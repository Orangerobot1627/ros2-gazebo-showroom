#!/usr/bin/env python3
"""Protect the public typed showroom interface contracts."""

from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]


def normalized(path):
    """Return non-comment, non-empty interface lines."""
    return [
        line.strip() for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.lstrip().startswith('#')
    ]


def main():
    status = normalized(PACKAGE / 'msg' / 'RobotStatus.msg')
    reset = normalized(PACKAGE / 'srv' / 'ResetRobotPose.srv')
    task = normalized(PACKAGE / 'action' / 'ExecuteShowroomTask.action')

    assert status[:3] == [
        'builtin_interfaces/Time stamp',
        'string robot_id',
        'string navigation_state',
    ]
    assert 'geometry_msgs/Pose2D pose' in status
    assert 'geometry_msgs/Twist command_velocity' in status
    assert 'float32 distance_remaining_m' in status
    assert reset == [
        'string robot_id',
        'geometry_msgs/Pose2D pose',
        '---',
        'bool success',
        'string message',
    ]
    assert task.count('---') == 2
    assert 'string intent' in task
    assert 'string plan_json' in task
    assert 'bool accepted' in task
    assert 'float32 progress' in task
    print('Message, service, and action interface contracts: OK')


if __name__ == '__main__':
    main()
