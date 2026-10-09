#!/usr/bin/env python3
"""
Regression test for the guide-priority coffee yield.

Feeds synthetic poses into the task manager and checks that the coffee robot
pauses only while the guide is inside the hold radius, resumes once the guide
clears the release radius, and never yields when it is idle.
"""

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
# Keep ROS logs writable even when $HOME is read-only (sandboxed CI).
os.environ.setdefault('ROS_LOG_DIR', tempfile.mkdtemp(prefix='showroom_ros_log_'))

import rclpy  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from showroom_task_manager import ShowroomTaskManager  # noqa: E402


def main():
    rclpy.init(args=[])
    node = ShowroomTaskManager()
    try:
        node.set_parameters([Parameter('yield_enabled', value=True)])
        logic = node.logic
        logic.guide_state = 'TOURING'
        logic.coffee_state = 'DELIVERING'

        # Both robots active but far apart: the coffee robot keeps moving.
        node.robot_poses = {'robot_0': (0.0, -14.5), 'robot_1': (10.0, 10.0)}
        node.evaluate_yield()
        assert logic.coffee_state == 'DELIVERING', logic.coffee_state
        assert node.coffee_yielding is False, node.coffee_yielding

        # The guide enters the hold radius: the coffee robot yields.
        node.robot_poses = {'robot_0': (1.0, 0.0), 'robot_1': (2.0, 0.0)}
        node.evaluate_yield()
        assert logic.coffee_state == 'PAUSED', logic.coffee_state
        assert node.coffee_yielding is True, node.coffee_yielding

        # Still inside the release radius: it stays paused.
        node.robot_poses = {'robot_0': (1.0, 0.0), 'robot_1': (3.0, 0.0)}
        node.evaluate_yield()
        assert logic.coffee_state == 'PAUSED', logic.coffee_state

        # The guide clears the release radius: the coffee robot resumes.
        node.robot_poses = {'robot_0': (0.0, 0.0), 'robot_1': (5.0, 0.0)}
        node.evaluate_yield()
        assert logic.coffee_state == 'DELIVERING', logic.coffee_state
        assert node.coffee_yielding is False, node.coffee_yielding

        # An idle coffee robot never yields, however close the guide is.
        logic.coffee_state = 'STANDBY'
        node.robot_poses = {'robot_0': (1.1, 0.0), 'robot_1': (1.0, 0.0)}
        node.evaluate_yield()
        assert logic.coffee_state == 'STANDBY', logic.coffee_state
        assert node.coffee_yielding is False, node.coffee_yielding

        # A paused-by-operator coffee robot is left alone.
        logic.coffee_state = 'PAUSED'
        node.coffee_yielding = False
        node.robot_poses = {'robot_0': (1.0, 0.0), 'robot_1': (1.2, 0.0)}
        node.evaluate_yield()
        assert logic.coffee_state == 'PAUSED', logic.coffee_state
        assert node.coffee_yielding is False, node.coffee_yielding
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print('Guide-priority coffee yield: OK')


if __name__ == '__main__':
    main()
