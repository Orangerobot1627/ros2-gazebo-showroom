#!/usr/bin/env python3
"""Validate metric invariants in the generated Gazebo showroom world."""

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / 'worlds' / 'showroom.sdf'


def load_generator():
    path = ROOT / 'scripts' / 'generate_showroom_world.py'
    specification = importlib.util.spec_from_file_location(
        'showroom_world_generator', path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main():
    generator = load_generator()
    generated_tree = generator.build_world()
    ET.indent(generated_tree, space='  ')
    installed_tree = ET.parse(WORLD)
    generated = ET.tostring(generated_tree.getroot())
    installed = ET.tostring(installed_tree.getroot())
    assert generated == installed, (
        'showroom.sdf is stale; rerun scripts/generate_showroom_world.py')

    root = installed_tree.getroot()
    world = root.find("./world[@name='showroom']")
    assert world is not None
    structure = world.find("./model[@name='showroom_structure']")
    assert structure is not None
    link = structure.find("./link[@name='structure']")
    assert link is not None

    floor_size = link.find(
        "./collision[@name='floor_collision']/geometry/box/size")
    assert floor_size is not None
    assert floor_size.text == '50.000 35.000 0.100'

    collisions = link.findall('./collision')
    visuals = link.findall('./visual')
    assert len(collisions) == 77
    assert len(visuals) == 84

    obstacle = world.find("./model[@name='test_obstacle']")
    assert obstacle is not None
    assert obstacle.findtext('pose') == '-2.0 -12.5 0.5 0 0 0'
    assert obstacle.findtext('static') == 'false'

    plugin_names = {
        plugin.get('name') for plugin in world.findall('./plugin')}
    assert plugin_names == {
        'gz::sim::systems::Physics',
        'gz::sim::systems::UserCommands',
        'gz::sim::systems::SceneBroadcaster',
        'gz::sim::systems::Sensors',
    }
    print('Gazebo showroom dimensions, geometry, and systems: OK')


if __name__ == '__main__':
    main()
