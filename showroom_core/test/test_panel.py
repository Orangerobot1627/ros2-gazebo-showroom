#!/usr/bin/env python3
"""Deterministic tests for the operator panel renderer."""

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def load_panel():
    """Load the panel module without starting a ROS node."""
    path = ROOT / 'scripts' / 'showroom_panel.py'
    spec = importlib.util.spec_from_file_location('showroom_panel', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE = {
    'type': 'showroom_monitor',
    'sequence': 12,
    'sim_time_sec': 42.0,
    'published_at': '2026-10-08T12:00:00.000+00:00',
    'business': {
        'guide_state': 'TOURING',
        'coffee_state': 'DELIVERING',
        'current_task': {
            'task_id': 'vision_hall', 'display_name': '计算机视觉展厅',
            'ordinal': 3, 'total': 7,
        },
        'active_plan': {
            'plan_id': 'plan-1', 'state': 'RUNNING',
            'current_step': 1, 'step_total': 3,
        },
    },
    'robots': {
        'robot_0': {
            'navigation_state': 'NAVIGATING',
            'route': 'guide_selected_route',
            'current_waypoint': 'vision_inside',
            'waypoint_index': 12,
            'waypoint_total': 64,
            'pose': {'x': -9.0, 'y': -7.7, 'yaw_deg': 180.0},
            'command_velocity': {'linear_x': 0.3, 'angular_z': 0.0},
            'front_clearance_m': 2.1,
            'blocked_duration_sec': 0.0,
            'block_count': 1,
            'recovery_state': 'READY',
            'nav2_feedback': {
                'distance_remaining_m': 1.5,
                'estimated_time_remaining_sec': 5.0,
                'number_of_recoveries': 0,
            },
            'last_event': 'waypoint_reached',
        },
        'robot_1': {
            'navigation_state': 'BLOCKED',
            'route': 'coffee_delivery_route',
            'current_waypoint': 'coffee_area',
            'waypoint_index': 4,
            'waypoint_total': 19,
            'pose': None,
            'command_velocity': {'linear_x': 0.0, 'angular_z': 0.0},
            'front_clearance_m': 0.4,
            'blocked_duration_sec': 3.2,
            'block_count': 2,
            'recovery_state': 'WAITING_FOR_CLEARANCE',
            'nav2_feedback': {},
            'last_event': 'blocked',
        },
    },
}


def main():
    panel = load_panel()

    text = panel.render_panel(SAMPLE)
    assert '展馆运行面板' in text
    assert '导览: 导览中' in text and '配送: 配送中' in text
    assert '计算机视觉展厅' in text and '3/7' in text
    assert 'plan-1' in text and 'RUNNING' in text
    assert '蓝色导览' in text and '导航中' in text
    assert 'vision_inside' in text and '12/64' in text
    assert '(-9.0, -7.7) 180.0' in text
    assert '前净空: 2.1 m' in text
    assert '绿色配送' in text and '受阻' in text and '等待清障' in text

    detail = panel.render_detail(SAMPLE)
    assert '"guide_state": "TOURING"' in detail
    assert '"waypoint_index": 12' in detail

    # Unknown states fall back to the raw value and missing fields do not crash.
    assert panel.label(panel.STATE_LABELS, 'WEIRD') == 'WEIRD'
    assert panel.label(panel.STATE_LABELS, None) == '-'
    minimal = panel.render_panel({})
    assert '展馆运行面板' in minimal

    print('Operator panel rendering: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
