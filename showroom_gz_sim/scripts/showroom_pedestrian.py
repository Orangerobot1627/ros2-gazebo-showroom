#!/usr/bin/env python3
"""
Walk the Gazebo pedestrian model back and forth along an open lobby line.

The showroom world contains a ``showroom_pedestrian`` model; this node drives it
kinematically by calling the bridged ``/world/showroom/set_pose`` service on a
fixed cadence, interpolating along a straight segment and reversing at each end
(with a short pause). A velocity-control walker was tried first but the floor
contact fought the commanded velocity, so teleport-stepping is used instead: it
is deterministic, physics free, and still shows a moving person for the robots
to notice and avoid.
"""

from geometry_msgs.msg import Pose
import rclpy
from rclpy.node import Node
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose


class ShowroomPedestrian(Node):
    """Drive one Gazebo model back and forth along a straight open line."""

    def __init__(self):
        super().__init__('showroom_pedestrian')
        self.declare_parameter('set_pose_service', '/world/showroom/set_pose')
        self.declare_parameter('entity_name', 'showroom_pedestrian')
        self.declare_parameter('start', [-5.5, -10.0])
        self.declare_parameter('end', [5.5, -10.0])
        self.declare_parameter('height', 0.62)
        self.declare_parameter('speed_mps', 0.6)
        self.declare_parameter('pause_sec', 1.5)

        start = [float(value)
                 for value in self.get_parameter('start').value]
        end = [float(value)
               for value in self.get_parameter('end').value]
        self.start = start
        self.end = end
        self.height = float(self.get_parameter('height').value)
        self.speed = max(0.05, abs(float(self.get_parameter('speed_mps').value)))
        self.pause = max(0.0, float(self.get_parameter('pause_sec').value))
        length = max(1e-3, ((end[0] - start[0]) ** 2
                            + (end[1] - start[1]) ** 2) ** 0.5)
        self.leg_sec = length / self.speed
        self.period = 2.0 * (self.leg_sec + self.pause)

        self.entity = Entity()
        self.entity.name = str(self.get_parameter('entity_name').value)
        self.entity.type = Entity.MODEL
        self.client = self.create_client(
            SetEntityPose, self.get_parameter('set_pose_service').value)
        self.started = self.now()
        self.create_timer(0.1, self.step)
        self.get_logger().info(
            f'Pedestrian walker: {length:.1f} m legs at {self.speed:.2f} m/s '
            f'via {self.get_parameter("set_pose_service").value}')

    def now(self):
        """Return the current clock time in seconds."""
        return self.get_clock().now().nanoseconds / 1e9

    def point_at(self, elapsed):
        """Return the (x, y) position for the given elapsed time."""
        phase = elapsed % self.period
        if phase < self.leg_sec:
            fraction = phase / self.leg_sec
            forward = True
        elif phase < self.leg_sec + self.pause:
            fraction = 1.0
            forward = True
        elif phase < 2.0 * self.leg_sec + self.pause:
            fraction = (phase - self.leg_sec - self.pause) / self.leg_sec
            forward = False
        else:
            fraction = 0.0
            forward = False
        if forward:
            ratio = fraction
        else:
            ratio = 1.0 - fraction
        x = self.start[0] + (self.end[0] - self.start[0]) * ratio
        y = self.start[1] + (self.end[1] - self.start[1]) * ratio
        return x, y

    def step(self):
        """Send the next pose to Gazebo."""
        if not self.client.service_is_ready():
            return
        x, y = self.point_at(self.now() - self.started)
        request = SetEntityPose.Request()
        request.entity = self.entity
        request.pose = Pose()
        request.pose.position.x = x
        request.pose.position.y = y
        request.pose.position.z = self.height
        request.pose.orientation.w = 1.0
        self.client.call_async(request)


def main(args=None):
    """Run the pedestrian walker until shutdown."""
    rclpy.init(args=args)
    node = ShowroomPedestrian()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
