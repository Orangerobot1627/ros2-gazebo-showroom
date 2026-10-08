#!/usr/bin/env python3
"""Validate the ROS and Gazebo descriptions against the frozen Stage robot."""

import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
URDF = ROOT / 'urdf' / 'showroom_robot.urdf.xacro'
SDF = ROOT / 'urdf' / 'showroom_robot.gazebo.xacro'
SAFETY_MARGIN_DEG = 5.0


def expand(path, *arguments):
    """Run xacro and return the expanded XML root."""
    result = subprocess.run(
        ['xacro', str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return ET.fromstring(result.stdout)


def require_text(root, path, expected):
    """Assert that an XML element exists with the expected text."""
    element = root.find(path)
    assert element is not None, path
    assert element.text.strip() == expected, (path, element.text, expected)


def visual_z_range(visual):
    """Return the (min, max) height of one axis-aligned primitive visual."""
    pose = visual.find('pose')
    z = 0.0
    if pose is not None and pose.text:
        values = pose.text.split()
        if len(values) >= 3:
            z = float(values[2])
    geometry = visual.find('geometry')
    cylinder = geometry.find('cylinder')
    sphere = geometry.find('sphere')
    box = geometry.find('box')
    if cylinder is not None:
        half = float(cylinder.find('length').text) / 2.0
    elif sphere is not None:
        half = float(sphere.find('radius').text)
    elif box is not None:
        half = float(box.find('size').text.split()[2]) / 2.0
    else:
        return None
    return z - half, z + half


def visual_xy_box(visual):
    """Return (cx, cy, half_x, half_y) of one axis-aligned visual."""
    pose = visual.find('pose')
    cx = cy = 0.0
    if pose is not None and pose.text:
        values = pose.text.split()
        if len(values) >= 2:
            cx, cy = float(values[0]), float(values[1])
    geometry = visual.find('geometry')
    cylinder = geometry.find('cylinder')
    sphere = geometry.find('sphere')
    box = geometry.find('box')
    if cylinder is not None:
        half = float(cylinder.find('radius').text)
        return cx, cy, half, half
    if sphere is not None:
        half = float(sphere.find('radius').text)
        return cx, cy, half, half
    if box is not None:
        size = box.find('size').text.split()
        return cx, cy, float(size[0]) / 2.0, float(size[1]) / 2.0
    return None


def assert_scan_plane_clear(model):
    """
    Fail if a body visual intrudes into the lidar field of view.

    Gazebo's gpu_lidar renders visual geometry, so any body part inside the
    +/-FOV/2 scan cone is reported as an obstacle at close range and trips the
    Nav2 collision monitor. A visual is only a problem when it both crosses the
    scan height and its horizontal footprint reaches into the scan cone; a thin
    part that stays outside the field of view is allowed.
    """
    scan_pose = model.find("./link[@name='base_scan']/pose")
    assert scan_pose is not None
    scan_values = scan_pose.text.split()
    lidar_x = float(scan_values[0])
    scan_z = float(scan_values[2])
    sensor = model.find("./link[@name='base_scan']/sensor")
    max_angle = float(sensor.find('ray/scan/horizontal/max_angle').text)
    fov_half_deg = abs(math.degrees(max_angle))

    base_link = model.find("./link[@name='base_link']")
    assert base_link is not None
    for visual in base_link.findall('visual'):
        limits = visual_z_range(visual)
        if limits is None:
            continue
        low, high = limits
        if not low < scan_z < high:
            continue
        box = visual_xy_box(visual)
        assert box is not None, visual.attrib.get('name')
        cx, cy, half_x, half_y = box
        angles = [
            abs(math.degrees(math.atan2(
                cy + sy * half_y, cx + sx * half_x - lidar_x)))
            for sx in (-1, 1)
            for sy in (-1, 1)
        ]
        smallest = min(angles)
        assert smallest > fov_half_deg + SAFETY_MARGIN_DEG, (
            'visual enters the lidar field of view', visual.attrib.get('name'),
            f'closest angle {smallest:.1f} deg <= {fov_half_deg:.1f} deg')


def main():
    """Check dimensions, sensor contract, drive plugins, and ROS frames."""
    urdf = expand(URDF)
    assert urdf.tag == 'robot'
    assert urdf.find("./link[@name='base_footprint']") is not None
    assert urdf.find("./link[@name='base_link']") is not None
    assert urdf.find("./link[@name='base_scan']") is not None
    assert urdf.find("./joint[@name='left_wheel_joint']") is not None
    assert urdf.find("./joint[@name='right_wheel_joint']") is not None
    scan_joint = urdf.find("./joint[@name='base_scan_joint']/origin")
    assert scan_joint is not None
    assert scan_joint.attrib['xyz'] == '0.18 0 0.50'

    sdf = expand(SDF, 'namespace:=robot_0', 'robot_name:=guide_robot')
    model = sdf.find("./model[@name='guide_robot']")
    assert model is not None
    require_text(
        model,
        "./link[@name='base_link']/collision[@name='body_collision']"
        '/geometry/box/size',
        '0.62 0.48 0.38',
    )
    require_text(
        model,
        "./link[@name='base_scan']/pose",
        '0.18 0 0.50 0 0 0',
    )
    assert_scan_plane_clear(model)
    require_text(
        model,
        "./link[@name='base_scan']/sensor[@name='showroom_lidar']"
        '/ray/scan/horizontal/samples',
        '540',
    )
    require_text(
        model,
        "./link[@name='base_scan']/sensor[@name='showroom_lidar']"
        '/ray/range/min',
        '0.05',
    )
    require_text(
        model,
        "./link[@name='base_scan']/sensor[@name='showroom_lidar']"
        '/ray/range/max',
        '12.0',
    )
    require_text(
        model,
        "./plugin[@name='gz::sim::systems::DiffDrive']/topic",
        '/robot_0/cmd_vel',
    )
    require_text(
        model,
        "./plugin[@name='gz::sim::systems::DiffDrive']/odom_topic",
        '/robot_0/odom',
    )
    require_text(
        model,
        "./plugin[@name='gz::sim::systems::DiffDrive']/child_frame_id",
        'robot_0/base_footprint',
    )
    coffee_sdf = expand(
        SDF,
        'namespace:=robot_1',
        'robot_name:=coffee_robot',
        'body_color:=0.10 0.70 0.30 1',
    )
    coffee = coffee_sdf.find("./model[@name='coffee_robot']")
    assert coffee is not None
    assert_scan_plane_clear(coffee)
    require_text(
        coffee,
        "./plugin[@name='gz::sim::systems::DiffDrive']/topic",
        '/robot_1/cmd_vel',
    )
    require_text(
        coffee,
        "./plugin[@name='gz::sim::systems::DiffDrive']/odom_topic",
        '/robot_1/odom',
    )
    require_text(
        coffee,
        "./plugin[@name='gz::sim::systems::DiffDrive']/child_frame_id",
        'robot_1/base_footprint',
    )
    require_text(
        coffee,
        "./link[@name='base_scan']/sensor[@name='showroom_lidar']/topic",
        '/robot_1/scan',
    )
    print('Stage dimensions and Gazebo robot interfaces: OK')


if __name__ == '__main__':
    main()
