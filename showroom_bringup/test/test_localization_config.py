#!/usr/bin/env python3
"""Validate the map and AMCL frame contract for the guide robot."""

import hashlib
from pathlib import Path

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE = PACKAGE.parents[2]
MAP_YAML = PACKAGE / 'maps' / 'showroom_final.yaml'
MAP_IMAGE = PACKAGE / 'maps' / 'showroom_final.pgm'
PARAMS = PACKAGE / 'config' / 'robot_0_nav2.yaml'
NAVIGATION_PARAMS = PACKAGE / 'config' / 'robot_0_navigation.yaml'
ROBOT_1_PARAMS = PACKAGE / 'config' / 'robot_1_nav2.yaml'
ROBOT_1_NAVIGATION_PARAMS = PACKAGE / 'config' / 'robot_1_navigation.yaml'
STAGE_IMAGE = (
    WORKSPACE / 'src' / 'sim_stage' / 'demo_stage' /
    'world' / 'maps' / 'showroom_final.pgm')
NAVIGATION_LAUNCH = PACKAGE / 'launch' / 'navigation.launch.py'
DUAL_ROBOT_LAUNCH = PACKAGE / 'launch' / 'dual_robot.launch.py'


def digest(path):
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pgm_dimensions(path):
    """Read the dimensions from a binary PGM header."""
    with path.open('rb') as stream:
        assert stream.readline().strip() == b'P5'
        line = stream.readline()
        while line.startswith(b'#'):
            line = stream.readline()
        return tuple(int(value) for value in line.split())


def main():
    """Ensure Gazebo localization preserves the accepted Stage coordinates."""
    map_data = yaml.safe_load(MAP_YAML.read_text(encoding='utf-8'))
    assert map_data['image'] == 'showroom_final.pgm'
    assert map_data['resolution'] == 0.05
    assert map_data['origin'] == [-25.0, -17.5, 0.0]
    assert pgm_dimensions(MAP_IMAGE) == (1000, 700)
    if STAGE_IMAGE.exists():
        assert digest(MAP_IMAGE) == digest(STAGE_IMAGE)

    params = yaml.safe_load(PARAMS.read_text(encoding='utf-8'))
    amcl = params['/robot_0/amcl']['ros__parameters']
    assert amcl['global_frame_id'] == 'map'
    assert amcl['odom_frame_id'] == 'robot_0/odom'
    assert amcl['base_frame_id'] == 'robot_0/base_footprint'
    assert amcl['initial_pose']['x'] == 0.0
    assert amcl['initial_pose']['y'] == -14.5
    assert abs(amcl['initial_pose']['yaw'] - 1.57079632679) < 1e-9

    navigation = yaml.safe_load(
        NAVIGATION_PARAMS.read_text(encoding='utf-8'))
    controller = navigation['controller_server']['ros__parameters']
    local = navigation['local_costmap']['local_costmap']['ros__parameters']
    global_map = (
        navigation['global_costmap']['global_costmap']['ros__parameters'])
    planner = navigation['planner_server']['ros__parameters']
    collision_monitor = navigation['collision_monitor']['ros__parameters']
    follow_path = controller['FollowPath']
    assert follow_path['plugin'] == 'dwb_core::DWBLocalPlanner'
    assert 'BaseObstacle' in follow_path['critics']
    assert 'Oscillation' in follow_path['critics']
    assert local['robot_base_frame'] == 'robot_0/base_footprint'
    assert local['global_frame'] == 'robot_0/odom'
    assert local['obstacle_layer']['scan']['topic'] == '/robot_0/scan'
    assert global_map['global_frame'] == 'map'
    assert global_map['static_layer']['map_topic'] == '/map'
    assert planner['GridBased']['use_astar'] is True
    assert collision_monitor['base_frame_id'] == 'robot_0/base_footprint'
    assert collision_monitor['odom_frame_id'] == 'robot_0/odom'
    assert collision_monitor['cmd_vel_in_topic'] == 'cmd_vel_smoothed'
    assert collision_monitor['cmd_vel_out_topic'] == 'cmd_vel'
    assert collision_monitor['scan']['topic'] == '/robot_0/scan'
    assert collision_monitor['SafetyStop']['action_type'] == 'stop'

    robot_1_params = yaml.safe_load(
        ROBOT_1_PARAMS.read_text(encoding='utf-8'))
    robot_1_amcl = robot_1_params['/robot_1/amcl']['ros__parameters']
    assert robot_1_amcl['odom_frame_id'] == 'robot_1/odom'
    assert robot_1_amcl['base_frame_id'] == 'robot_1/base_footprint'
    assert robot_1_amcl['initial_pose']['x'] == 2.3
    assert robot_1_amcl['initial_pose']['y'] == -14.5

    robot_1_navigation = yaml.safe_load(
        ROBOT_1_NAVIGATION_PARAMS.read_text(encoding='utf-8'))
    robot_1_bt = robot_1_navigation['bt_navigator']['ros__parameters']
    robot_1_local = (
        robot_1_navigation['local_costmap']['local_costmap'][
            'ros__parameters'])
    robot_1_collision_monitor = (
        robot_1_navigation['collision_monitor']['ros__parameters'])
    assert robot_1_bt['robot_base_frame'] == 'robot_1/base_footprint'
    assert robot_1_bt['odom_topic'] == '/robot_1/odom'
    assert robot_1_local['obstacle_layer']['scan']['topic'] == '/robot_1/scan'
    assert robot_1_collision_monitor['base_frame_id'] == (
        'robot_1/base_footprint')
    assert robot_1_collision_monitor['odom_frame_id'] == 'robot_1/odom'
    assert robot_1_collision_monitor['scan']['topic'] == '/robot_1/scan'

    navigation_launch = NAVIGATION_LAUNCH.read_text(encoding='utf-8')
    assert "package='nav2_collision_monitor'" in navigation_launch
    assert "'collision_monitor'," in navigation_launch
    assert "('cmd_vel_smoothed', 'cmd_vel_smoothed')" in navigation_launch

    dual_robot_launch = DUAL_ROBOT_LAUNCH.read_text(encoding='utf-8')
    assert "get_package_share_directory('showroom_core')" in dual_robot_launch
    assert "get_package_share_directory('showroom_interaction')" in (
        dual_robot_launch)
    assert "DeclareLaunchArgument('business_mode', default_value='true')" in (
        dual_robot_launch)
    assert "'auto_start': business_auto_start" in dual_robot_launch
    assert "DeclareLaunchArgument('enable_llm', default_value='false')" in (
        dual_robot_launch)
    assert "DeclareLaunchArgument('enable_voice', default_value='false')" in (
        dual_robot_launch)
    assert "DeclareLaunchArgument('enable_pose_reset', default_value='true')" \
        in dual_robot_launch
    assert "'enable_pose_reset': enable_pose_reset" in dual_robot_launch
    assert "'llm_backend': llm_backend" in dual_robot_launch
    print('Map, Nav2, business, and interaction launch contracts: OK')


if __name__ == '__main__':
    main()
