#!/usr/bin/env python3
"""Validate simulator-independent monitor state transitions and topics."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from showroom_monitor import RobotState  # noqa: E402


def main():
    """Exercise Nav2 block, recovery, and completion monitoring."""
    robot = RobotState('robot_1')
    robot.handle_event({
        'type': 'route_started',
        'robot_id': 'robot_1',
        'route': 'coffee_delivery_route',
        'total': 12,
        'stamp': 10.0,
    }, 10.0)
    robot.handle_navigation_status({
        'active': True,
        'finished': False,
        'blocked': True,
        'blocked_since_sec': 12.0,
        'block_count': 1,
        'front_clearance_m': 0.35,
    }, 15.0)
    blocked = robot.snapshot(15.0)
    assert blocked['navigation_state'] == 'BLOCKED'
    assert blocked['blocked_duration_sec'] == 3.0
    assert blocked['front_clearance_m'] == 0.35

    robot.handle_navigation_status({
        'active': True,
        'finished': False,
        'blocked': False,
        'last_blocked_duration_sec': 3.5,
        'block_count': 1,
    }, 15.5)
    resumed = robot.snapshot(15.5)
    assert resumed['navigation_state'] == 'NAVIGATING'
    assert resumed['recovery_state'] == 'RESUMED_AFTER_CLEARANCE'
    assert resumed['recovery_policy'] == (
        'NAV2_COLLISION_MONITOR_AUTO_RESUME')

    source = (ROOT / 'scripts' / 'showroom_monitor.py').read_text(
        encoding='utf-8')
    assert 'lookup_transform(' in source
    assert "'map', f'{robot_id}/base_link'" in source
    assert "f'/{robot_id}/scan'" in source
    assert 'from showroom_interfaces.msg import RobotStatus' in source
    assert "'typed_status_topic', '/showroom/robot_status'" in source
    assert 'self.typed_status_publisher.publish(status)' in source
    assert 'ground_truth' not in source
    print('Gazebo/Nav2 monitor state and topic contracts: OK')


if __name__ == '__main__':
    main()
