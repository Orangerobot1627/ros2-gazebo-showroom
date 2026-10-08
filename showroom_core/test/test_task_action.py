#!/usr/bin/env python3
"""Deterministic tests for the typed ExecuteShowroomTask control plane."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from showroom_interfaces.action import ExecuteShowroomTask  # noqa: E402
from showroom_task_manager import ShowroomTaskManager  # noqa: E402


def goal(**fields):
    """Build one ExecuteShowroomTask goal with the given fields set."""
    request = ExecuteShowroomTask.Goal()
    for key, value in fields.items():
        setattr(request, key, value)
    return request


def main():
    document = ShowroomTaskManager.document_from_task_request(
        goal(intent='start_tour', coffee=True))
    assert document == {'intent': 'start_tour', 'coffee': True}, document

    document = ShowroomTaskManager.document_from_task_request(
        goal(intent='deliver_drink', robot='coffee', target='robotics',
             drink='coffee'))
    assert document == {
        'intent': 'deliver_drink', 'robot': 'coffee',
        'target': 'robotics', 'drink': 'coffee'}, document

    document = ShowroomTaskManager.document_from_task_request(
        goal(action='pause', robot='guide', duration_sec=30.0))
    assert document == {
        'intent': 'robot_action', 'action': 'pause',
        'robot': 'guide', 'duration_sec': 30.0}, document

    document = ShowroomTaskManager.document_from_task_request(
        goal(request_id='plan-9', plan_json='[{"action":"pause"}]'))
    assert document['intent'] == 'execute_plan', document
    assert document['plan_id'] == 'plan-9', document
    assert document['plan'] == [{'action': 'pause'}], document

    document = ShowroomTaskManager.document_from_task_request(
        goal(intent='visit_only', tasks=['vision_hall', 'dance_hall']))
    assert document['tasks'] == ['vision_hall', 'dance_hall'], document

    # An empty goal carries no intent, so the accept callback rejects it.
    assert not ShowroomTaskManager.document_from_task_request(
        goal()).get('intent')

    print('ExecuteShowroomTask control-plane mapping: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
