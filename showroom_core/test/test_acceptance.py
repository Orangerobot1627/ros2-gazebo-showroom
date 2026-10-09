#!/usr/bin/env python3
"""
Regression test for the headless acceptance recorder.

Feeds synthetic business events, Nav2 telemetry and a lidar scan straight into
the recorder callbacks and checks the folded report: waypoint counting with
synthetic phase events excluded, the terminal route_completed flag, the
recovery/safety maxima and the minimum lidar clearance.
"""

import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
# Keep ROS logs writable even when $HOME is read-only (sandboxed CI).
os.environ.setdefault('ROS_LOG_DIR', tempfile.mkdtemp(prefix='showroom_ros_log_'))

import rclpy  # noqa: E402
from sensor_msgs.msg import LaserScan  # noqa: E402
from showroom_acceptance import AcceptanceRecorder  # noqa: E402
from std_msgs.msg import String  # noqa: E402


def event(**fields):
    message = String()
    message.data = json.dumps(fields)
    return message


def scan(ranges, range_min=0.05):
    message = LaserScan()
    message.range_min = range_min
    message.ranges = ranges
    return message


def options(report_path):
    return SimpleNamespace(
        robot='robot_1',
        event_topic='/showroom/robot_events',
        telemetry_topic='/showroom/navigation_status',
        command_topic='/showroom/command',
        scan_topic=['/robot_1/scan'],
        command=None,
        command_delay_sec=3.0,
        timeout_sec=600.0,
        report=str(report_path),
    )


def main():
    rclpy.init()
    report_path = Path(tempfile.mkdtemp()) / 'report.json'
    node = AcceptanceRecorder(options(report_path))
    try:
        # A different robot's events must be ignored entirely.
        node.on_event(event(type='waypoint_reached', robot_id='robot_0',
                            label='entrance'))

        node.on_event(event(type='route_started', robot_id='robot_1',
                            route='coffee_delivery_route',
                            mission_id='delivery-0009', total=14))
        for label in ('coffee_robot_standby', 'leave_standby',
                      'coffee_pickup'):
            node.on_event(event(type='waypoint_reached', robot_id='robot_1',
                                label=label))
        # Synthetic phase events must not count as navigation waypoints.
        node.on_event(event(type='waypoint_reached', robot_id='robot_1',
                            label='depart_pickup'))
        node.on_event(event(type='waypoint_reached', robot_id='robot_1',
                            label='coffee_south_east'))
        node.on_event(event(type='waypoint_reached', robot_id='robot_1',
                            label='return_from_delivery'))

        node.on_telemetry(event(type='navigation_status', robot_id='robot_1',
                                block_count=2,
                                action_feedback={'number_of_recoveries': 3}))
        node.on_telemetry(event(type='navigation_status', robot_id='robot_1',
                                block_count=1,
                                action_feedback={'number_of_recoveries': 5}))

        node.on_scan(scan([1.2, float('inf'), 0.42, 3.0, float('nan'), -1.0]))

        node.on_event(event(type='route_completed', robot_id='robot_1',
                            mission_id='delivery-0009'))
        node.write_report()

        report = json.loads(report_path.read_text(encoding='utf-8'))
        assert report['result'] == 'completed', report
        assert report['route_completed'] is True, report
        assert report['waypoints_completed'] == 4, report['waypoints']
        assert report['waypoints_expected'] == 14, report
        assert report['waypoints'] == [
            'coffee_robot_standby', 'leave_standby', 'coffee_pickup',
            'coffee_south_east'], report['waypoints']
        assert report['recoveries'] == 5, report
        assert report['safety_interventions'] == 2, report
        assert report['min_lidar_clearance_m'] == 0.42, report
        assert report['route'] == 'coffee_delivery_route', report
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print('Acceptance recorder metric folding: OK')


if __name__ == '__main__':
    main()
