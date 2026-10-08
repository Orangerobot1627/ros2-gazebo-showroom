#!/usr/bin/env python3
"""
Smooth accelerate/decelerate shaping for showroom velocity commands.

The profiler sits between the Nav2 velocity smoother and the collision monitor.
It rate-limits the command up (acceleration) and down (deceleration), clamps it
to configured maxima, and reduces forward speed while turning so the robot eases
through corners instead of lurching. The shaping is pure logic so it can be
unit tested without ROS.
"""

from geometry_msgs.msg import Twist
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class SpeedProfiler:
    """Shape raw velocity commands into a smooth accelerate/decelerate profile."""

    def __init__(self, max_linear=0.55, max_angular=1.20,
                 linear_accel=0.70, linear_decel=0.90,
                 angular_accel=2.0, angular_decel=2.5,
                 turn_slowdown_gain=0.6, min_turn_speed_scale=0.35):
        if max_linear <= 0.0 or max_angular <= 0.0:
            raise ValueError('Velocity limits must be positive')
        if min(linear_accel, linear_decel, angular_accel, angular_decel) <= 0.0:
            raise ValueError('Acceleration and deceleration must be positive')
        if not 0.0 <= turn_slowdown_gain <= 1.0:
            raise ValueError('turn_slowdown_gain must be within [0, 1]')
        if not 0.0 < min_turn_speed_scale <= 1.0:
            raise ValueError('min_turn_speed_scale must be within (0, 1]')
        self.max_linear = float(max_linear)
        self.max_angular = float(max_angular)
        self.linear_accel = float(linear_accel)
        self.linear_decel = float(linear_decel)
        self.angular_accel = float(angular_accel)
        self.angular_decel = float(angular_decel)
        self.turn_slowdown_gain = float(turn_slowdown_gain)
        self.min_turn_speed_scale = float(min_turn_speed_scale)
        self.linear = 0.0
        self.angular = 0.0

    @staticmethod
    def _clamp(value, limit):
        return max(-limit, min(limit, value))

    @staticmethod
    def _approach(current, target, accel, decel, dt):
        if target >= current:
            return min(target, current + accel * dt)
        return max(target, current - decel * dt)

    def reset(self):
        """Drop the current command to a full stop."""
        self.linear = 0.0
        self.angular = 0.0

    def turn_scale(self, target_angular):
        """Forward-speed scale for the requested turn rate."""
        ratio = abs(float(target_angular)) / self.max_angular
        return max(self.min_turn_speed_scale, 1.0 - self.turn_slowdown_gain * ratio)

    def step(self, target_linear, target_angular, dt):
        """Return the shaped (linear, angular) command for one time step."""
        dt = max(0.0, float(dt))
        target_linear = self._clamp(float(target_linear), self.max_linear)
        target_angular = self._clamp(float(target_angular), self.max_angular)
        target_linear *= self.turn_scale(target_angular)
        self.linear = self._approach(
            self.linear, target_linear, self.linear_accel,
            self.linear_decel, dt)
        self.angular = self._approach(
            self.angular, target_angular, self.angular_accel,
            self.angular_decel, dt)
        return self.linear, self.angular


class ShowroomSpeedProfile(Node):
    """Shape ``cmd_vel_smoothed`` into a smooth ``cmd_vel_profiled`` stream."""

    def __init__(self):
        super().__init__('showroom_speed_profile')
        self.declare_parameter('input_topic', 'cmd_vel_smoothed')
        self.declare_parameter('output_topic', 'cmd_vel_profiled')
        self.declare_parameter('max_linear', 0.55)
        self.declare_parameter('max_angular', 1.20)
        self.declare_parameter('linear_accel', 0.70)
        self.declare_parameter('linear_decel', 0.90)
        self.declare_parameter('angular_accel', 2.0)
        self.declare_parameter('angular_decel', 2.5)
        self.declare_parameter('turn_slowdown_gain', 0.6)
        self.declare_parameter('min_turn_speed_scale', 0.35)
        self.profiler = SpeedProfiler(
            max_linear=float(self.get_parameter('max_linear').value),
            max_angular=float(self.get_parameter('max_angular').value),
            linear_accel=float(self.get_parameter('linear_accel').value),
            linear_decel=float(self.get_parameter('linear_decel').value),
            angular_accel=float(self.get_parameter('angular_accel').value),
            angular_decel=float(self.get_parameter('angular_decel').value),
            turn_slowdown_gain=float(
                self.get_parameter('turn_slowdown_gain').value),
            min_turn_speed_scale=float(
                self.get_parameter('min_turn_speed_scale').value),
        )
        self.last_time = None
        self.publisher = self.create_publisher(
            Twist, self.get_parameter('output_topic').value, 10)
        self.create_subscription(
            Twist, self.get_parameter('input_topic').value,
            self.command_callback, 10)
        self.get_logger().info(
            'Speed profile active: '
            f'{self.get_parameter("input_topic").value} -> '
            f'{self.get_parameter("output_topic").value}')

    def command_callback(self, message):
        now = self.get_clock().now().nanoseconds / 1e9
        dt = 0.0 if self.last_time is None else max(0.0, now - self.last_time)
        self.last_time = now
        linear, angular = self.profiler.step(
            message.linear.x, message.angular.z, dt)
        shaped = Twist()
        shaped.linear.x = linear
        shaped.angular.z = angular
        self.publisher.publish(shaped)


def main(args=None):
    """Run the showroom speed-profile node."""
    rclpy.init(args=args)
    node = ShowroomSpeedProfile()
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
