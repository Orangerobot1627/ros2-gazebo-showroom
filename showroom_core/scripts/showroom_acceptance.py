#!/usr/bin/env python3
"""
Headless acceptance recorder for one showroom navigation run.

It subscribes to the business navigation event stream, the per-robot Nav2
telemetry and the lidar scans, then writes a single JSON report with the
metrics the acceptance checklist asks for:

* how many waypoints were reached (and their order),
* which targets failed and why,
* the Nav2 recovery count and safety/obstacle interventions,
* the wall-clock duration,
* the minimum lidar clearance,
* whether ``route_completed`` was observed.

The node can inject the mission trigger command itself, then exits as soon as
the tracked robot reports ``route_completed`` or ``route_failed`` (or
``--timeout-sec`` elapses). The exit status is 0 only for a completed route,
so a shell loop can measure the success rate directly.
"""

import argparse
import json
import math
from pathlib import Path
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy, qos_profile_sensor_data, QoSProfile, ReliabilityPolicy)
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


def event_qos():
    """Return the QoS used by the durable showroom event/status topics."""
    return QoSProfile(
        depth=200,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )


# Synthetic phase events the adapter emits around a pickup/delivery hand-off;
# they are not navigation waypoints, so they never count toward the total.
SYNTHETIC_LABELS = frozenset({'depart_pickup', 'return_from_delivery'})


class AcceptanceRecorder(Node):
    """Collect one run's navigation metrics and write an acceptance report."""

    def __init__(self, options):
        super().__init__('showroom_acceptance')
        self.options = options
        self.robot_id = options.robot
        self.report_path = Path(options.report)
        self.qos = event_qos()
        self.started_at = time.monotonic()
        self.finished_at = None
        self.result = None
        self.route = None
        self.mission_id = None
        self.expected_waypoints = None
        self.waypoints = []
        self.failures = []
        self.route_completed = False
        self.recoveries = 0
        self.safety_interventions = 0
        self.min_clearance = math.inf
        self.command_sent = False

        self.create_subscription(
            String, options.event_topic, self.on_event, self.qos)
        self.create_subscription(
            String, options.telemetry_topic, self.on_telemetry, self.qos)
        for topic in options.scan_topic:
            self.create_subscription(
                LaserScan, topic, self.on_scan, qos_profile_sensor_data)
        self.command_publisher = None
        if options.command:
            self.command_publisher = self.create_publisher(
                String, options.command_topic, self.qos)
        self.get_logger().info(
            f'Acceptance recorder tracking {self.robot_id} -> '
            f'{self.report_path}')

    def on_event(self, message):
        """Fold one business navigation event into the run metrics."""
        try:
            document = json.loads(message.data)
        except (json.JSONDecodeError, TypeError):
            return
        if document.get('robot_id') != self.robot_id:
            return
        if document.get('route'):
            self.route = document['route']
        if document.get('mission_id'):
            self.mission_id = document['mission_id']
        if isinstance(document.get('total'), int):
            self.expected_waypoints = document['total']
        event_type = document.get('type')
        if event_type == 'waypoint_reached':
            label = document.get('label')
            if label and label not in SYNTHETIC_LABELS:
                self.waypoints.append(label)
        elif event_type == 'route_completed':
            self.route_completed = True
            self.finish('completed')
        elif event_type == 'route_failed':
            self.failures.append({
                'target': document.get('target') or document.get('label'),
                'reason': document.get('reason'),
            })
            self.finish('failed')

    def on_telemetry(self, message):
        """Track the Nav2 recovery and safety-intervention counters."""
        try:
            document = json.loads(message.data)
        except (json.JSONDecodeError, TypeError):
            return
        if document.get('robot_id') != self.robot_id:
            return
        feedback = document.get('action_feedback') or {}
        try:
            recoveries = int(feedback.get('number_of_recoveries') or 0)
        except (TypeError, ValueError):
            recoveries = 0
        self.recoveries = max(self.recoveries, recoveries)
        try:
            self.safety_interventions = max(
                self.safety_interventions,
                int(document.get('block_count') or 0))
        except (TypeError, ValueError):
            pass

    def on_scan(self, message):
        """Track the smallest finite lidar range seen during the run."""
        for value in message.ranges:
            if value is None or not math.isfinite(value):
                continue
            if value <= 0.0 or value < message.range_min:
                continue
            if value < self.min_clearance:
                self.min_clearance = value

    def send_command(self):
        """Publish the mission trigger command exactly once."""
        if self.command_publisher is None or self.command_sent:
            return
        message = String()
        message.data = self.options.command
        self.command_publisher.publish(message)
        self.command_sent = True
        self.get_logger().info(f'Acceptance command sent: {message.data}')

    def finish(self, result):
        """Mark the run finished once, keeping the first terminal outcome."""
        if self.finished_at is not None:
            return
        self.result = result
        self.finished_at = time.monotonic()

    def report(self):
        """Build the JSON-serialisable acceptance report."""
        finished = self.finished_at or time.monotonic()
        return {
            'robot_id': self.robot_id,
            'route': self.route,
            'mission_id': self.mission_id,
            'result': self.result or 'timeout',
            'route_completed': self.route_completed,
            'waypoints_completed': len(self.waypoints),
            'waypoints_expected': self.expected_waypoints,
            'waypoints': self.waypoints,
            'failures': self.failures,
            'recoveries': self.recoveries,
            'safety_interventions': self.safety_interventions,
            'duration_sec': round(finished - self.started_at, 2),
            'min_lidar_clearance_m': (
                round(self.min_clearance, 3)
                if math.isfinite(self.min_clearance) else None),
            'started_at': self.started_at,
            'finished_at': finished,
        }

    def write_report(self):
        """Persist the acceptance report and log a one-line verdict."""
        document = self.report()
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding='utf-8')
        self.get_logger().info(
            'Acceptance result: {result} | waypoints {done}/{expected} | '
            'recoveries {rec} | safety {safe} | {dur:.1f}s | min clearance '
            '{clr}'.format(
                result=document['result'],
                done=document['waypoints_completed'],
                expected=document['waypoints_expected'],
                rec=document['recoveries'],
                safe=document['safety_interventions'],
                dur=document['duration_sec'],
                clr=document['min_lidar_clearance_m']))


def parse_args(argv=None):
    """Parse the recorder command line."""
    parser = argparse.ArgumentParser(
        description='Record one showroom acceptance run to a JSON report.')
    parser.add_argument('--robot', default='robot_0',
                        help='robot id to track (default: robot_0)')
    parser.add_argument('--event-topic', default='/showroom/robot_events')
    parser.add_argument('--telemetry-topic',
                        default='/showroom/navigation_status')
    parser.add_argument('--command-topic', default='/showroom/command')
    parser.add_argument('--scan-topic', action='append',
                        default=None,
                        help='lidar topic(s); repeatable '
                             '(default: /<robot>/scan)')
    parser.add_argument('--command', default=None,
                        help='mission trigger command as a JSON string')
    parser.add_argument('--command-delay-sec', type=float, default=3.0,
                        help='delay before publishing the command')
    parser.add_argument('--timeout-sec', type=float, default=900.0)
    parser.add_argument('--report', default='logs/acceptance/report.json')
    options = parser.parse_args(argv)
    if not options.scan_topic:
        options.scan_topic = [f'/{options.robot}/scan']
    return options


def run(options, spin_until_done=rclpy.spin_once):
    """Run the recorder loop; returns the process exit code."""
    node = AcceptanceRecorder(options)
    deadline = time.monotonic() + options.timeout_sec
    command_at = (time.monotonic() + options.command_delay_sec
                  if options.command else None)
    try:
        while rclpy.ok() and node.finished_at is None:
            spin_until_done(node, timeout_sec=0.2)
            now = time.monotonic()
            if command_at is not None and now >= command_at:
                node.send_command()
            if now >= deadline:
                node.finish('timeout')
    except (KeyboardInterrupt, ExternalShutdownException):
        node.finish('interrupted')
    finally:
        node.write_report()
        exit_code = 0 if node.route_completed else 1
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return exit_code


def main(argv=None):
    """Entry point for the acceptance recorder."""
    options = parse_args(argv)
    rclpy.init()
    return run(options)


if __name__ == '__main__':
    raise SystemExit(main())
