#!/usr/bin/env python3
"""Explicit control-priority ladder for the showroom task tree.

The task tree arbitrates three levels for the guide robot:

    DEFAULT_ITINERARY   the accepted tour the robot was asked to run
    TEMPORARY_VISIT     a bounded visitor detour that suspends the itinerary
    HUMAN_OVERRIDE      a timed human takeover (pause / manual action)

A higher level temporarily suspends the one below and restores it when it ends.
This module makes that arbitration observable in status messages and panels; it
is pure logic with no ROS dependency so it can be unit tested directly.
"""

PRIORITY_RANKS = {
    'IDLE': 0,
    'DEFAULT_ITINERARY': 1,
    'TEMPORARY_VISIT': 2,
    'HUMAN_OVERRIDE': 3,
}

HUMAN_OVERRIDE_DETAIL = (
    'human override lease active; the default mission resumes on release')
TEMPORARY_VISIT_DETAIL = (
    'temporary visit active; the saved itinerary restores afterwards')
DEFAULT_ITINERARY_DETAIL = 'default accepted mission'
IDLE_DETAIL = 'no active mission'


def control_priority(override_robots, temporary_active, active_robots):
    """Return the control-priority snapshot for the task tree.

    ``override_robots`` are robots under a human override lease,
    ``temporary_active`` marks an in-flight temporary visit, and
    ``active_robots`` are robots running their default mission.
    """
    override_robots = sorted(set(override_robots))
    active_robots = sorted(set(active_robots))
    if override_robots:
        level = 'HUMAN_OVERRIDE'
        detail = HUMAN_OVERRIDE_DETAIL
        robots = override_robots
    elif temporary_active:
        level = 'TEMPORARY_VISIT'
        detail = TEMPORARY_VISIT_DETAIL
        robots = ['robot_0']
    elif active_robots:
        level = 'DEFAULT_ITINERARY'
        detail = DEFAULT_ITINERARY_DETAIL
        robots = active_robots
    else:
        level = 'IDLE'
        detail = IDLE_DETAIL
        robots = []
    return {
        'level': level,
        'rank': PRIORITY_RANKS[level],
        'robots': robots,
        'detail': detail,
    }
