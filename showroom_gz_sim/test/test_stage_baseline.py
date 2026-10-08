#!/usr/bin/env python3
"""Protect the accepted Stage-to-Gazebo migration baseline from silent drift."""

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE = PACKAGE.parents[2]
BASELINE = PACKAGE / 'migration' / 'stage_baseline.json'
STAGE = WORKSPACE / 'src' / 'sim_stage' / 'demo_stage'


def sha256(path):
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    """Validate fixed contracts and source hashes when Stage is present."""
    data = json.loads(BASELINE.read_text(encoding='utf-8'))
    assert data['route_waypoint_counts']['guide_full_route'] == 65
    assert data['route_waypoint_counts']['coffee_delivery_route'] == 19
    assert len(data['task_units']) == 7
    assert data['guide_robot']['body_size_m'] == [0.62, 0.48, 0.38]
    assert data['guide_robot']['lidar']['samples'] == 540
    assert data['coffee_event_sequence'][0] == 'route_started'
    assert data['coffee_event_sequence'][-1] == 'route_completed'

    if STAGE.exists():
        for relative, expected in data['source_files'].items():
            source = STAGE / relative
            assert source.is_file(), source
            assert sha256(source) == expected, relative

    print('Stage migration behavior and source hashes: OK')


if __name__ == '__main__':
    main()
