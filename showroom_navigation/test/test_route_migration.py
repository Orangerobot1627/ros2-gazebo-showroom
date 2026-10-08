#!/usr/bin/env python3
"""Verify that the Gazebo route keeps the accepted Stage guide geometry."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE_ROUTES = (
    ROOT.parents[1] / 'sim_stage' / 'demo_stage' / 'config' / 'routes.yaml'
)


def guide_waypoints(path):
    document = yaml.safe_load(path.read_text(encoding='utf-8'))
    return document['routes']['guide_full_route']['waypoints']


def main():
    migrated = guide_waypoints(ROOT / 'config' / 'routes.yaml')
    assert len(migrated) == 65
    assert migrated[0] == {'x': 0.0, 'y': -14.5, 'label': 'entrance'}
    assert migrated[-1]['label'] == 'guide_destination'
    assert len({item['label'] for item in migrated}) == 65

    if STAGE_ROUTES.exists():
        accepted = guide_waypoints(STAGE_ROUTES)
        assert migrated == accepted, 'Gazebo migration changed the Stage route'

    print('Stage-to-Gazebo guide route parity: OK (65 waypoints)')


if __name__ == '__main__':
    main()
