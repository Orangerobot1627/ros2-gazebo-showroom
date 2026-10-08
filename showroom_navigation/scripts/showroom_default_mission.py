#!/usr/bin/env python3
"""Publish the accepted default showroom guide mission on request or startup."""

import json
import uuid

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


DEFAULT_TASK_IDS = [
    'reception',
    'technology_history',
    'vision_hall',
    'robotics_hall',
    'time_tunnel',
    'dance_hall',
    'lounge',
]


class ShowroomDefaultMission(Node):
    """Own the default itinerary without coupling it to Gazebo or Nav2."""

    def __init__(self):
        super().__init__('showroom_default_mission')
        self.declare_parameter(
            'request_topic', '/showroom/navigation_requests')
        self.declare_parameter('robot_id', 'robot_0')
        self.declare_parameter('start', 'entrance')
        self.declare_parameter('task_ids', DEFAULT_TASK_IDS)
        self.declare_parameter('autostart', False)
        self.declare_parameter('startup_delay_sec', 3.0)

        qos = QoSProfile(
            depth=20,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.publisher = self.create_publisher(
            String, self.get_parameter('request_topic').value, qos)
        self.timer = None
        if self.get_parameter('autostart').value:
            delay = max(
                0.1,
                float(self.get_parameter('startup_delay_sec').value),
            )
            self.timer = self.create_timer(delay, self.publish_once)
            self.get_logger().info(
                f'Default guide mission will start in {delay:.1f} s')
        else:
            self.get_logger().info(
                'Default guide autostart is disabled; waiting for a request')

    def publish_once(self):
        if self.timer is not None:
            self.timer.cancel()
            self.destroy_timer(self.timer)
            self.timer = None
        document = {
            'request_type': 'guide_itinerary',
            'robot_id': str(self.get_parameter('robot_id').value),
            'mission_id': f'gazebo-guide-{uuid.uuid4().hex[:8]}',
            'start': str(self.get_parameter('start').value),
            'task_ids': list(self.get_parameter('task_ids').value),
        }
        message = String()
        message.data = json.dumps(
            document, ensure_ascii=False, separators=(',', ':'))
        self.publisher.publish(message)
        self.get_logger().info(
            f'Published default guide mission {document["mission_id"]}: '
            f'{len(document["task_ids"])} task units')


def main(args=None):
    rclpy.init(args=args)
    node = ShowroomDefaultMission()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
