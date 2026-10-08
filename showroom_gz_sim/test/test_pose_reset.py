#!/usr/bin/env python3
"""Validate the Gazebo bridge and safe pose-reset proxy contracts."""

from pathlib import Path

import yaml


PACKAGE = Path(__file__).resolve().parents[1]


def main():
    """Check the service bridge, model mapping, stop, and AMCL reset path."""
    bridges = yaml.safe_load(
        (PACKAGE / 'config' / 'ros_gz_bridge.yaml').read_text(
            encoding='utf-8'))
    pose_bridges = [
        entry for entry in bridges
        if entry.get('service_name') == '/world/showroom/set_pose'
    ]
    assert pose_bridges == [{
        'service_name': '/world/showroom/set_pose',
        'ros_type_name': 'ros_gz_interfaces/srv/SetEntityPose',
        'gz_req_type_name': 'gz.msgs.Pose',
        'gz_rep_type_name': 'gz.msgs.Boolean',
    }]

    source = (
        PACKAGE / 'scripts' / 'showroom_reset_pose.py').read_text(
            encoding='utf-8')
    launch = (
        PACKAGE / 'launch' / 'showroom_world.launch.py').read_text(
            encoding='utf-8')
    assert "'robot_0': 'guide_robot'" in source
    assert "'robot_1': 'coffee_robot'" in source
    assert "String, '/showroom/route_commands'" in source
    assert "Twist, f'/{robot_id}/cmd_vel'" in source
    assert "f'/{robot_id}/initialpose'" in source
    assert 'Entity.MODEL' in source
    assert 'MultiThreadedExecutor(num_threads=4)' in source
    assert "executable='showroom_reset_pose.py'" in launch
    assert "'enable_pose_reset', default_value='true'" in launch
    print('Gazebo set_pose bridge and reset safety contracts: OK')


if __name__ == '__main__':
    main()
