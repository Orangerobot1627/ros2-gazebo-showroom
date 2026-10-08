#!/usr/bin/env python3
"""Deterministic tests for the control-priority ladder."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from showroom_priority import (  # noqa: E402
    control_priority,
    PRIORITY_RANKS,
)


def main():
    idle = control_priority([], False, [])
    assert idle['level'] == 'IDLE', idle
    assert idle['rank'] == 0 and idle['robots'] == [], idle

    default = control_priority([], False, ['robot_0'])
    assert default['level'] == 'DEFAULT_ITINERARY', default
    assert default['rank'] == 1 and default['robots'] == ['robot_0'], default

    both = control_priority([], False, ['robot_1', 'robot_0'])
    assert both['robots'] == ['robot_0', 'robot_1'], both

    temporary = control_priority([], True, ['robot_0'])
    assert temporary['level'] == 'TEMPORARY_VISIT', temporary
    assert temporary['rank'] == 2, temporary

    override = control_priority(['robot_1'], True, ['robot_0'])
    assert override['level'] == 'HUMAN_OVERRIDE', override
    assert override['rank'] == 3 and override['robots'] == ['robot_1'], override

    assert (PRIORITY_RANKS['IDLE'] < PRIORITY_RANKS['DEFAULT_ITINERARY']
            < PRIORITY_RANKS['TEMPORARY_VISIT']
            < PRIORITY_RANKS['HUMAN_OVERRIDE'])
    assert idle['detail'] and override['detail']
    print('Control-priority ladder: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
