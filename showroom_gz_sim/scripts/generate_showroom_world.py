#!/usr/bin/env python3
"""Generate a Gazebo SDF world from the metric Stage showroom geometry."""

from dataclasses import dataclass
import math
from pathlib import Path
import xml.etree.ElementTree as ET


WIDTH_M = 50.0
HEIGHT_M = 35.0
WALL_HEIGHT = 2.50
OUTPUT = Path(__file__).resolve().parents[1] / 'worlds' / 'showroom.sdf'


@dataclass(frozen=True)
class Material:
    ambient: str
    diffuse: str


WALL = Material('0.52 0.56 0.62 1', '0.70 0.74 0.80 1')
TUNNEL_WALL = Material('0.12 0.18 0.30 1', '0.18 0.28 0.48 1')
COFFEE = Material('0.23 0.12 0.07 1', '0.48 0.25 0.12 1')
DISPLAY = Material('0.12 0.30 0.46 1', '0.18 0.48 0.72 1')
ROBOTICS = Material('0.24 0.25 0.28 1', '0.42 0.45 0.50 1')
DANCE = Material('0.34 0.12 0.46 1', '0.62 0.24 0.78 1')
FURNITURE = Material('0.25 0.27 0.30 1', '0.42 0.45 0.50 1')
PLANT = Material('0.06 0.25 0.08 1', '0.10 0.48 0.14 1')


def sub(parent, tag, text=None, **attributes):
    element = ET.SubElement(parent, tag, attributes)
    if text is not None:
        element.text = str(text)
    return element


def material_element(parent, material):
    node = sub(parent, 'material')
    sub(node, 'ambient', material.ambient)
    sub(node, 'diffuse', material.diffuse)
    sub(node, 'specular', '0.08 0.08 0.08 1')


def geometry_box(parent, size):
    geometry = sub(parent, 'geometry')
    box = sub(geometry, 'box')
    sub(box, 'size', ' '.join(f'{value:.3f}' for value in size))


def geometry_cylinder(parent, radius, length):
    geometry = sub(parent, 'geometry')
    cylinder = sub(geometry, 'cylinder')
    sub(cylinder, 'radius', f'{radius:.3f}')
    sub(cylinder, 'length', f'{length:.3f}')


def add_box(link, name, x, y, size_x, size_y, height, yaw=0.0,
            material=WALL, collision=True, z=None):
    center_z = height / 2.0 if z is None else z
    pose = f'{x:.3f} {y:.3f} {center_z:.3f} 0 0 {yaw:.6f}'
    if collision:
        collision_node = sub(link, 'collision', name=f'{name}_collision')
        sub(collision_node, 'pose', pose)
        geometry_box(collision_node, (size_x, size_y, height))
    visual = sub(link, 'visual', name=f'{name}_visual')
    sub(visual, 'pose', pose)
    geometry_box(visual, (size_x, size_y, height))
    material_element(visual, material)
    sub(visual, 'cast_shadows', 'true' if height > 0.10 else 'false')


def add_cylinder(link, name, x, y, radius, height, material,
                 collision=True):
    pose = f'{x:.3f} {y:.3f} {height / 2.0:.3f} 0 0 0'
    if collision:
        collision_node = sub(link, 'collision', name=f'{name}_collision')
        sub(collision_node, 'pose', pose)
        geometry_cylinder(collision_node, radius, height)
    visual = sub(link, 'visual', name=f'{name}_visual')
    sub(visual, 'pose', pose)
    geometry_cylinder(visual, radius, height)
    material_element(visual, material)


def horizontal_wall(name, y, x0, x1, thickness=0.30,
                    material=WALL):
    return (
        name, (x0 + x1) / 2.0, y, abs(x1 - x0), thickness, material)


def vertical_wall(name, x, y0, y1, thickness=0.30,
                  material=WALL):
    return (
        name, x, (y0 + y1) / 2.0, thickness, abs(y1 - y0), material)


WALLS = [
    horizontal_wall('outer_north', 16.8, -24.7, 24.7, 0.35),
    vertical_wall('outer_west', -24.7, -16.8, 16.8, 0.35),
    vertical_wall('outer_east', 24.7, -16.8, 16.8, 0.35),
    horizontal_wall('outer_south_west', -16.8, -24.7, -3.5, 0.35),
    horizontal_wall('outer_south_east', -16.8, 3.5, 24.7, 0.35),
    vertical_wall('entrance_west', -3.5, -16.8, -13.8, 0.25),
    vertical_wall('entrance_east', 3.5, -16.8, -13.8, 0.25),
    horizontal_wall('entrance_lobby_west', -13.8, -24.7, -3.5),
    horizontal_wall('entrance_lobby_east', -13.8, 3.5, 24.7),
    horizontal_wall('vision_north_west', -3.2, -24.7, -17.0),
    horizontal_wall('vision_north_east', -3.2, -13.2, -8.0),
    vertical_wall('vision_entry_south', -8.0, -13.8, -9.0),
    vertical_wall('vision_entry_north', -8.0, -6.5, -3.2),
    horizontal_wall('robotics_south_west', 3.5, -24.7, -13.2),
    horizontal_wall('robotics_south_east', 3.5, -10.0, -8.0),
    vertical_wall('robotics_east_south', -8.0, 3.5, 10.8),
    vertical_wall('robotics_east_north', -8.0, 13.2, 16.8),
    horizontal_wall('tunnel_south', 9.0, -6.0, 6.0,
                    material=TUNNEL_WALL),
    vertical_wall('tunnel_west_south', -6.0, 9.0, 10.8,
                  material=TUNNEL_WALL),
    vertical_wall('tunnel_west_north', -6.0, 13.2, 16.8,
                  material=TUNNEL_WALL),
    vertical_wall('tunnel_east_south', 6.0, 9.0, 10.8,
                  material=TUNNEL_WALL),
    vertical_wall('tunnel_east_north', 6.0, 13.2, 16.8,
                  material=TUNNEL_WALL),
    vertical_wall('tunnel_baffle_west', -2.0, 9.0, 13.0, 0.25,
                  material=TUNNEL_WALL),
    vertical_wall('tunnel_baffle_east', 2.0, 13.0, 16.8, 0.25,
                  material=TUNNEL_WALL),
    # Dance/lounge partition: one aligned wall with a single centred door.
    # It used to be two walls 1 m apart (y=3.5 and y=2.5) with doors offset by
    # 2 m, which made the robot zig-zag through a sliver; merge them at y=3.0.
    horizontal_wall('dance_lounge_west', 3.0, 8.0, 12.5),
    horizontal_wall('dance_lounge_east', 3.0, 16.5, 24.7),
    vertical_wall('dance_west_south', 8.0, 3.0, 10.8),
    vertical_wall('dance_west_north', 8.0, 13.2, 16.8),
    vertical_wall('lounge_west_south', 8.0, -13.8, -9.2),
    vertical_wall('lounge_west_north', 8.0, -6.3, 3.0),
]


HISTORY_PANELS = [
    ('history_north', 0.0, 5.15, 0),
    ('history_north_east', 3.65, 3.65, 45),
    ('history_east', 5.15, 0.0, 90),
    ('history_south_east', 3.65, -3.65, 135),
    ('history_south', 0.0, -5.15, 0),
    ('history_south_west', -3.65, -3.65, 45),
    ('history_west', -5.15, 0.0, 90),
    ('history_north_west', -3.65, 3.65, 135),
]


HALL_DISPLAYS = [
    ('vision_west', -21.5, -5.2, 2.5, 0.35, 90, DISPLAY),
    ('vision_south_west', -19.0, -12.5, 3.0, 0.35, 0, DISPLAY),
    ('vision_south_east', -12.5, -12.5, 2.8, 0.35, 0, DISPLAY),
    ('vision_east', -10.0, -5.0, 2.3, 0.35, 90, DISPLAY),
    ('robotics_west', -22.0, 7.0, 2.2, 0.35, 90, ROBOTICS),
    ('robotics_north_west', -20.0, 14.8, 3.0, 0.35, 0, ROBOTICS),
    ('robotics_north_east', -12.0, 14.8, 2.8, 0.35, 0, ROBOTICS),
    ('robotics_east', -10.0, 7.0, 2.0, 0.35, 90, ROBOTICS),
    ('dance_north_west', 10.0, 14.8, 2.3, 0.35, 0, DANCE),
    ('dance_north_east', 19.5, 14.8, 3.0, 0.35, 0, DANCE),
    ('dance_east', 22.5, 8.0, 2.6, 0.35, 90, DANCE),
    ('dance_south', 18.5, 4.5, 2.8, 0.35, 0, DANCE),
]


FURNITURE_BOXES = [
    ('lounge_desk', 19.4, -1.3, 2.8, 1.0),
    ('lounge_east_sofa', 21.5, -4.75, 1.4, 2.5),
    ('lounge_south_sofa', 19.0, -10.95, 3.0, 1.1),
    ('lounge_south_table', 13.5, -12.05, 3.0, 0.9),
    ('lounge_center_bench', 14.5, -6.6, 2.0, 0.8),
]


PLANTS = [
    (-7.2, -12.8), (-6.0, 2.5), (-7.0, 7.5), (-7.0, 15.0),
    (7.0, 15.0), (7.0, 7.0), (8.0, -12.5), (8.0, -2.5),
    (-22.5, -1.0), (-22.5, 1.5), (-5.5, -7.5), (7.0, -12.0),
    (-5.5, 7.5), (5.5, 7.5),
]


ZONES = [
    ('entrance', 0.0, -15.3, 6.6, 2.6, '0.20 0.45 0.80 0.28'),
    ('vision', -16.4, -8.5, 16.0, 10.1, '0.15 0.45 0.75 0.20'),
    ('robotics', -16.4, 10.1, 16.0, 12.8, '0.34 0.36 0.40 0.20'),
    ('history', 0.0, 0.0, 14.0, 17.0, '0.76 0.55 0.18 0.16'),
    ('tunnel', 0.0, 13.0, 11.7, 7.3, '0.15 0.22 0.42 0.28'),
    ('dance', 16.4, 10.1, 16.0, 12.8, '0.55 0.20 0.66 0.20'),
    ('lounge', 16.8, -5.5, 15.4, 15.6, '0.20 0.62 0.43 0.18'),
]


def add_dynamic_test_obstacle(world):
    model = sub(world, 'model', name='test_obstacle')
    sub(model, 'pose', '-2.0 -12.5 0.5 0 0 0')
    sub(model, 'static', 'false')
    link = sub(model, 'link', name='body')
    inertial = sub(link, 'inertial')
    sub(inertial, 'mass', '8.0')
    inertia = sub(inertial, 'inertia')
    sub(inertia, 'ixx', '0.8533')
    sub(inertia, 'iyy', '0.8533')
    sub(inertia, 'izz', '0.8533')
    collision = sub(link, 'collision', name='collision')
    geometry_box(collision, (0.8, 0.8, 1.0))
    visual = sub(link, 'visual', name='visual')
    geometry_box(visual, (0.8, 0.8, 1.0))
    material_element(
        visual, Material('0.80 0.12 0.02 1', '1.00 0.24 0.04 1'))


def build_world():
    sdf = ET.Element('sdf', {'version': '1.10'})
    world = sub(sdf, 'world', name='showroom')

    physics = sub(world, 'physics', name='showroom_physics', type='ignored')
    sub(physics, 'max_step_size', '0.005')
    sub(physics, 'real_time_factor', '1.0')
    sub(physics, 'real_time_update_rate', '200')
    sub(world, 'gravity', '0 0 -9.8')

    sub(world, 'plugin', filename='gz-sim-physics-system',
        name='gz::sim::systems::Physics')
    sub(world, 'plugin', filename='gz-sim-user-commands-system',
        name='gz::sim::systems::UserCommands')
    sub(world, 'plugin', filename='gz-sim-scene-broadcaster-system',
        name='gz::sim::systems::SceneBroadcaster')
    sensors = sub(
        world, 'plugin', filename='gz-sim-sensors-system',
        name='gz::sim::systems::Sensors')
    sub(sensors, 'render_engine', 'ogre2')

    scene = sub(world, 'scene')
    sub(scene, 'ambient', '0.52 0.54 0.58 1')
    sub(scene, 'background', '0.08 0.10 0.14 1')
    sub(scene, 'shadows', 'true')

    sun = sub(world, 'light', name='sun', type='directional')
    sub(sun, 'pose', '0 0 12 0 0 0')
    sub(sun, 'cast_shadows', 'true')
    sub(sun, 'intensity', '0.85')
    sub(sun, 'direction', '-0.3 0.2 -0.9')

    structure = sub(world, 'model', name='showroom_structure')
    sub(structure, 'static', 'true')
    link = sub(structure, 'link', name='structure')

    add_box(
        link, 'floor', 0.0, 0.0, WIDTH_M, HEIGHT_M, 0.10,
        material=Material('0.30 0.32 0.35 1', '0.46 0.49 0.53 1'),
        z=-0.05)

    for name, x, y, size_x, size_y, color in ZONES:
        add_box(
            link, f'zone_{name}', x, y, size_x, size_y, 0.006,
            material=Material(color, color), collision=False, z=0.004)

    for name, x, y, size_x, size_y, material in WALLS:
        add_box(link, name, x, y, size_x, size_y, WALL_HEIGHT,
                material=material)

    add_cylinder(link, 'coffee_bar', 0.0, 0.0, 3.60, 1.05, COFFEE)
    add_cylinder(link, 'vision_globe', -16.0, -8.5, 1.40, 1.60, DISPLAY)
    add_cylinder(
        link, 'robotics_display', -16.0, 9.5, 1.70, 1.45, ROBOTICS)
    add_cylinder(link, 'dance_stage', 16.0, 9.5, 2.35, 0.45, DANCE)

    for name, x, y, degrees in HISTORY_PANELS:
        add_box(
            link, name, x, y, 1.30, 0.22, 1.40,
            yaw=math.radians(degrees), material=DISPLAY)

    for name, x, y, size_x, size_y, degrees, material in HALL_DISPLAYS:
        add_box(
            link, name, x, y, size_x, size_y, 1.60,
            yaw=math.radians(degrees), material=material)

    for name, x, y, size_x, size_y in FURNITURE_BOXES:
        add_box(
            link, name, x, y, size_x, size_y, 0.80,
            material=FURNITURE)
    add_cylinder(link, 'lounge_round_table', 14.5, -2.0, 0.55, 0.75,
                 FURNITURE)

    for index, (x, y) in enumerate(PLANTS, start=1):
        add_cylinder(
            link, f'plant_{index:02d}', x, y, 0.35, 1.20, PLANT)

    add_dynamic_test_obstacle(world)
    return ET.ElementTree(sdf)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tree = build_world()
    ET.indent(tree, space='  ')
    tree.write(OUTPUT, encoding='utf-8', xml_declaration=True)
    print(f'Generated Gazebo showroom: {OUTPUT}')
    print(f'Floor: {WIDTH_M:.1f} x {HEIGHT_M:.1f} m; walls: {len(WALLS)}')


if __name__ == '__main__':
    main()
