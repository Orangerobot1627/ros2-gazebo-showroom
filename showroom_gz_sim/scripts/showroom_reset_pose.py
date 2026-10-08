#!/usr/bin/env python3
"""Expose a validated showroom pose-reset service backed by Gazebo."""

import json
import math
import threading

from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose
from showroom_interfaces.srv import ResetRobotPose
from std_msgs.msg import String


class ShowroomPoseReset(Node):
    """Cancel motion, teleport a Gazebo model, and reinitialize AMCL."""

    ROBOTS = {
        'robot_0': 'guide_robot',
        'robot_1': 'coffee_robot',
    }

    def __init__(self):
        super().__init__('showroom_pose_reset')
        self.declare_parameter(
            'service_name', '/showroom/reset_robot_pose')
        self.declare_parameter(
            'gazebo_service_name', '/world/showroom/set_pose')
        self.declare_parameter('min_x', -24.5)
        self.declare_parameter('max_x', 24.5)
        self.declare_parameter('min_y', -17.0)
        self.declare_parameter('max_y', 17.0)
        self.declare_parameter('model_z', 0.02)
        self.declare_parameter('request_timeout_sec', 3.0)

        self.callback_group = ReentrantCallbackGroup()
        self.gz_client = self.create_client(
            SetEntityPose,
            self.get_parameter('gazebo_service_name').value,
            callback_group=self.callback_group,
        )
        self.reset_service = self.create_service(
            ResetRobotPose,
            self.get_parameter('service_name').value,
            self.reset_callback,
            callback_group=self.callback_group,
        )
        durable = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.route_command_publisher = self.create_publisher(
            String, '/showroom/route_commands', durable)
        self.velocity_publishers = {
            robot_id: self.create_publisher(
                Twist, f'/{robot_id}/cmd_vel', 10)
            for robot_id in self.ROBOTS
        }
        self.initial_pose_publishers = {
            robot_id: self.create_publisher(
                PoseWithCovarianceStamped,
                f'/{robot_id}/initialpose',
                durable,
            )
            for robot_id in self.ROBOTS
        }
        self.get_logger().info(
            'Pose reset ready on /showroom/reset_robot_pose')

    def validate(self, request):
        """Validate robot identity, finite values, and map bounds."""
        if request.robot_id not in self.ROBOTS:
            raise ValueError(
                f'unknown robot_id {request.robot_id!r}; '
                f'expected one of {tuple(self.ROBOTS)}')
        values = (request.pose.x, request.pose.y, request.pose.theta)
        if not all(math.isfinite(value) for value in values):
            raise ValueError('pose values must be finite')
        bounds = {
            'x': (
                float(self.get_parameter('min_x').value),
                float(self.get_parameter('max_x').value),
                request.pose.x,
            ),
            'y': (
                float(self.get_parameter('min_y').value),
                float(self.get_parameter('max_y').value),
                request.pose.y,
            ),
        }
        for axis, (minimum, maximum, value) in bounds.items():
            if not minimum <= value <= maximum:
                raise ValueError(
                    f'{axis}={value:.3f} is outside '
                    f'[{minimum:.3f}, {maximum:.3f}]')

    def stop_robot(self, robot_id):
        """Cancel the semantic route and force the final velocity to zero."""
        command = String()
        command.data = json.dumps({
            'type': 'route_command',
            'robot_id': robot_id,
            'action': 'cancel',
            'reason': 'pose_reset',
        }, separators=(',', ':'))
        self.route_command_publisher.publish(command)
        self.velocity_publishers[robot_id].publish(Twist())

    def gazebo_request(self, request):
        """Build the Gazebo service request for one robot model."""
        gazebo_request = SetEntityPose.Request()
        gazebo_request.entity.name = self.ROBOTS[request.robot_id]
        gazebo_request.entity.type = Entity.MODEL
        gazebo_request.pose.position.x = request.pose.x
        gazebo_request.pose.position.y = request.pose.y
        gazebo_request.pose.position.z = float(
            self.get_parameter('model_z').value)
        half_yaw = request.pose.theta * 0.5
        gazebo_request.pose.orientation.z = math.sin(half_yaw)
        gazebo_request.pose.orientation.w = math.cos(half_yaw)
        return gazebo_request

    def publish_initial_pose(self, request):
        """Tell the namespaced AMCL instance about the teleported pose."""
        message = PoseWithCovarianceStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'map'
        message.pose.pose.position.x = request.pose.x
        message.pose.pose.position.y = request.pose.y
        half_yaw = request.pose.theta * 0.5
        message.pose.pose.orientation.z = math.sin(half_yaw)
        message.pose.pose.orientation.w = math.cos(half_yaw)
        message.pose.covariance[0] = 0.25
        message.pose.covariance[7] = 0.25
        message.pose.covariance[35] = 0.0685
        self.initial_pose_publishers[request.robot_id].publish(message)

    def reset_callback(self, request, response):
        """Perform one bounded synchronous reset over the async bridge."""
        try:
            self.validate(request)
            timeout = float(
                self.get_parameter('request_timeout_sec').value)
            if not self.gz_client.wait_for_service(timeout_sec=timeout):
                raise RuntimeError('Gazebo set_pose service is unavailable')
            self.stop_robot(request.robot_id)
            future = self.gz_client.call_async(self.gazebo_request(request))
            completed = threading.Event()
            future.add_done_callback(lambda _future: completed.set())
            if not completed.wait(timeout):
                raise RuntimeError('Gazebo set_pose request timed out')
            gazebo_response = future.result()
            if gazebo_response is None or not gazebo_response.success:
                raise RuntimeError('Gazebo rejected the pose reset')
            self.publish_initial_pose(request)
            response.success = True
            response.message = (
                f'{request.robot_id} reset to '
                f'({request.pose.x:.3f}, {request.pose.y:.3f}, '
                f'{request.pose.theta:.3f})')
            self.get_logger().info(response.message)
        except (RuntimeError, ValueError) as exception:
            response.success = False
            response.message = str(exception)
            self.get_logger().warning(
                f'Pose reset rejected: {response.message}')
        return response


def main(args=None):
    """Run the reset proxy with enough threads for the nested client call."""
    rclpy.init(args=args)
    node = ShowroomPoseReset()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
