#!/usr/bin/env python3
"""Route-planning regression: task-manager requests -> gateway plans.

Runs the real task manager to build the navigation requests it would publish,
then feeds those through the semantic gateway planners and asserts the concrete
targets, waypoints and mission phases. No simulator is required.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]          # showroom_core
WORKSPACE = ROOT.parent                              # showroom_gz
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(WORKSPACE / 'showroom_navigation' / 'scripts'))

import rclpy  # noqa: E402
from ament_index_python.packages import (  # noqa: E402
    get_package_share_directory)
from showroom_navigation import (  # noqa: E402
    build_delivery_plan,
    build_guide_plan,
    build_temporary_visit_plan,
    GraphRoutePlanner,
)
from showroom_task_manager import ShowroomTaskManager  # noqa: E402
from showroom_task_units import TaskUnitCatalog  # noqa: E402


def plan(request, planner, catalog):
    """Resolve one navigation request into a gateway plan document."""
    kind = request['request_type']
    if kind == 'guide_itinerary':
        return build_guide_plan(planner, request, catalog)
    if kind == 'delivery':
        return build_delivery_plan(planner, request)
    if kind == 'temporary_visit':
        return build_temporary_visit_plan(planner, request, catalog)
    raise AssertionError(f'unexpected request type {kind!r}')


def reset(node):
    """Return the task manager to a clean guide-touring, coffee-idle state."""
    node.logic.reset()
    node.logic.guide_state = 'TOURING'
    node.temporary_guide = None
    node.guide_restore_mission_id = None


def main():
    rclpy.init(args=[])
    node = ShowroomTaskManager()
    try:
        share = Path(get_package_share_directory('showroom_navigation'))
        planner = GraphRoutePlanner.from_files(
            share / 'config' / 'navigation_graph.yaml',
            share / 'config' / 'routes.yaml')
        catalog = TaskUnitCatalog.from_files(
            share / 'config' / 'task_units.yaml',
            share / 'config' / 'routes.yaml')

        # 1) The full accepted itinerary plans end to end in exhibit order.
        reset(node)
        node.logic.guide_state = 'IDLE'
        effect = node.guide_navigation_effect(
            [unit.task_id for unit in node.task_units.catalog.units])
        guide = plan(effect, planner, catalog)
        assert guide['request_type'] == 'guide_itinerary', guide['request_type']
        assert guide['nodes'][-1] == 'guide_destination', guide['nodes'][-1]
        assert len(guide['waypoints']) > 55, len(guide['waypoints'])
        assert guide['distance_m'] > 100.0, guide['distance_m']

        # 2) Delivery to the first exhibit has pickup/delivery/standby phases.
        reset(node)
        delivery_effect, unit = node.delivery_effect(
            'technology_history', 'coffee')
        delivery = plan(delivery_effect, planner, catalog)
        assert delivery['request_type'] == 'delivery', delivery
        assert delivery['service_target'] == 'technology_history', delivery
        assert 'coffee_pickup' in delivery['nodes']
        phases = [
            waypoint.get('mission_phase') for waypoint in delivery['waypoints']]
        for phase in ('pickup', 'delivery', 'standby'):
            assert phase in phases, (phase, phases)
        pickup = delivery['nodes'].index('coffee_pickup')
        assert delivery['waypoints'][pickup]['mission_phase'] == 'pickup'

        # 3) A temporary visit reaches the requested venue and marks it.
        reset(node)
        visit_effect, unit = node.start_temporary_visit(
            'time_tunnel', dwell_sec=30.0)
        visit = plan(visit_effect, planner, catalog)
        assert visit['request_type'] == 'temporary_visit', visit
        assert visit['target_task'] == 'time_tunnel', visit
        assert visit['nodes'][-1] == 'hidden_door_approach', visit['nodes'][-1]
        assert visit['waypoints'][-1]['task_phase'] == 'temporary_destination'

        # 4) A rendezvous sends the guide and the coffee robot to one venue.
        reset(node)
        effects, detail = node.execute_rendezvous('vision_hall', dwell_sec=20.0)
        assert len(effects) == 2, effects
        guide_effect = next(
            item for item in effects if item['robot_id'] == 'robot_0')
        coffee_effect = next(
            item for item in effects if item['robot_id'] == 'robot_1')
        guide_plan = plan(guide_effect, planner, catalog)
        coffee_plan = plan(coffee_effect, planner, catalog)
        assert guide_plan['target_task'] == 'vision_hall', guide_plan
        assert guide_plan['nodes'][-1] == 'vision_hall_entry', \
            guide_plan['nodes'][-1]
        assert coffee_plan['service_target'] == 'vision_hall', coffee_plan
        assert coffee_plan['nodes'][-1] == 'coffee_robot_standby', \
            coffee_plan['nodes'][-1]
        assert '会和' in detail, detail

        # 5) A guide edit may use the validated connectors for a short cut.
        reset(node)
        edit_effect = node.guide_navigation_effect(
            ['vision_hall', 'lounge'], allow_shortcuts=True)
        edited = plan(edit_effect, planner, catalog)
        assert edited['cost_profile'] == 'smart', edited['cost_profile']
        assert edited['waypoints'], edited

        # 6) A busy coffee robot rejects the whole rendezvous cleanly.
        reset(node)
        node.logic.coffee_state = 'DELIVERING'
        try:
            node.execute_rendezvous('vision_hall')
        except ValueError:
            pass
        else:
            raise AssertionError('busy coffee robot must reject the rendezvous')
        assert node.temporary_guide is None
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print('Mission planning (requests -> gateway plans): OK')


if __name__ == '__main__':
    main()
