#!/usr/bin/env python3
"""Learn per-edge traversal times from the semantic route event stream.

Subscribes to ``/showroom/robot_events``, measures the simulated time between
consecutive ``waypoint_reached`` events per robot, folds it into an
``EdgeTimeModel``, and periodically saves the model so the route gateway can use
it. This is the lightweight, online analogue of the Nav2 Route Server
TimeMarker / TimeScorer pair: the route cost is auto-calibrated from how long
edges actually take instead of being set entirely by hand.
"""

import json

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from showroom_edge_times import EdgeTimeModel
from std_msgs.msg import String


class ShowroomEdgeRecorder(Node):
    """Record simulated traversal time for each consecutive waypoint pair."""

    def __init__(self):
        super().__init__('showroom_edge_recorder')
        self.declare_parameter('events_topic', '/showroom/robot_events')
        self.declare_parameter('output_file', '')
        self.declare_parameter('alpha', 0.4)
        self.declare_parameter('save_period_sec', 5.0)
        self.output_file = str(
            self.get_parameter('output_file').value).strip()
        self.model = EdgeTimeModel(
            alpha=float(self.get_parameter('alpha').value))
        self.last = {}
        qos = QoSProfile(
            depth=50,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            String, self.get_parameter('events_topic').value,
            self.event_callback, qos)
        period = float(self.get_parameter('save_period_sec').value)
        if period > 0.0:
            self.create_timer(period, self.save)
        self.get_logger().info(
            f'Edge recorder ready (output={self.output_file or "none"})')

    def now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def event_callback(self, message):
        try:
            event = json.loads(message.data)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        event_type = event.get('type')
        robot_id = event.get('robot_id')
        label = event.get('label')
        if event_type == 'route_started' and robot_id:
            self.last.pop(robot_id, None)
            return
        if event_type != 'waypoint_reached' or not robot_id or not label:
            return
        stamp = self.now()
        previous = self.last.get(robot_id)
        self.last[robot_id] = (label, stamp)
        if previous is None or previous[0] == label:
            return
        self.model.record(f'{previous[0]}->{label}', stamp - previous[1])

    def save(self):
        if not self.output_file:
            return
        try:
            self.model.save(self.output_file)
        except OSError as exception:
            self.get_logger().warning(f'Could not save edge times: {exception}')


def main(args=None):
    """Run the showroom edge-time recorder."""
    rclpy.init(args=args)
    node = ShowroomEdgeRecorder()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.save()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
