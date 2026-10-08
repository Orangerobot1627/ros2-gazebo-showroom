#!/usr/bin/env python3
"""Validate Gazebo and RViz route visualization geometry."""

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def load_visualizer():
    """Load the visualizer module from the source tree."""
    path = ROOT / 'scripts' / 'showroom_route_visualizer.py'
    spec = importlib.util.spec_from_file_location('route_visualizer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    """Check route counts, colors, SDF geometry, and beacon geometry."""
    visualizer = load_visualizer()
    routes, colors = visualizer.load_route_catalog(
        ROOT / 'config' / 'routes.yaml',
        ROOT / 'config' / 'task_units.yaml')
    assert len(routes[visualizer.GUIDE_ROUTE]) == 65
    assert len(routes[visualizer.COFFEE_ROUTE]) == 19
    assert colors['entrance'] != colors['history_panel_1']
    assert colors['vision_hall_entry'] != colors['dance_inside']
    codes = visualizer.build_waypoint_codes(routes)
    assert codes[(visualizer.GUIDE_ROUTE, 'entrance')] == 'G01'
    assert codes[(visualizer.GUIDE_ROUTE, 'guide_destination')] == 'G65'
    assert codes[(visualizer.COFFEE_ROUTE, 0)] == 'C01'
    assert codes[(visualizer.COFFEE_ROUTE, 'coffee_robot_standby')] == 'C19'
    assert visualizer.progress_text(
        'robot_0', 'NAVIGATING', 'stairs_clearance', 0, 64,
        codes) == 'GUIDE 1/64  G02  stairs_clearance'
    assert visualizer.progress_text(
        'robot_1', 'COMPLETED', None, 18, 18,
        codes) == 'COFFEE COMPLETED  18/18'
    assert visualizer.gazebo_progress_code(
        'robot_0', 'NAVIGATING', 'stairs_clearance', 0, 64,
        codes) == 'G02 1/64'
    marker = visualizer.build_gazebo_progress_marker(
        1, routes[visualizer.GUIDE_ROUTE][1], 'GUIDE 1/64',
        (1.0, 0.92, 0.05))
    assert marker.type == marker.LINE_LIST
    assert len(marker.point) > 20
    assert marker.pose.position.x == 0.0
    assert marker.pose.position.y == -10.62
    assert marker.pose.position.z == 1.42

    route_sdf = ET.fromstring(
        visualizer.build_gazebo_route_sdf(routes, colors))
    names = {
        node.attrib['name'] for node in route_sdf.findall('.//visual')}
    assert len([name for name in names if name.startswith(
        'guide_waypoint_')]) == 65
    assert len([name for name in names if name.startswith(
        'guide_segment_')]) == 64
    assert len([name for name in names if name.startswith(
        'coffee_waypoint_')]) == 19
    assert len([name for name in names if name.startswith(
        'coffee_segment_')]) == 18
    assert not route_sdf.findall('.//collision')

    beacon = ET.fromstring(visualizer.build_beacon_sdf(
        'guide_target_beacon', (1.0, 0.9, 0.1, 1.0)))
    assert beacon.find(".//model[@name='guide_target_beacon']") is not None
    assert len(beacon.findall('.//visual')) == 4
    for visual in beacon.findall('.//visual'):
        pose = visual.find('pose')
        z = float(pose.text.split()[2])
        cylinder = visual.find('geometry/cylinder')
        if cylinder is not None:
            half = float(cylinder.find('length').text) / 2.0
        else:
            half = float(visual.find('geometry/sphere/radius').text)
        assert not z - half < 0.50 < z + half, (
            'beacon visual crosses the lidar plane', visual.attrib.get('name'))
    print('Gazebo and RViz route visualization: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
