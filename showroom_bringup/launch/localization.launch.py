#!/usr/bin/env python3
"""Start the shared map server and guide-robot AMCL localization."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Create one global map and one namespaced AMCL instance."""
    bringup_share = get_package_share_directory('showroom_bringup')
    default_map = os.path.join(
        bringup_share, 'maps', 'showroom_final.yaml')
    default_params = os.path.join(
        bringup_share, 'config', 'robot_0_nav2.yaml')

    map_yaml = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    robot_namespace = LaunchConfiguration('robot_namespace')
    start_map_server = LaunchConfiguration('start_map_server')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')

    return LaunchDescription([
        DeclareLaunchArgument('map', default_value=default_map),
        DeclareLaunchArgument('params_file', default_value=default_params),
        DeclareLaunchArgument(
            'robot_namespace', default_value='robot_0'),
        DeclareLaunchArgument(
            'start_map_server', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('autostart', default_value='true'),
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            output='screen',
            parameters=[
                params_file,
                {'use_sim_time': use_sim_time, 'yaml_filename': map_yaml},
            ],
            condition=IfCondition(start_map_server),
        ),
        Node(
            package='nav2_amcl',
            executable='amcl',
            namespace=robot_namespace,
            name='amcl',
            output='screen',
            parameters=[params_file, {'use_sim_time': use_sim_time}],
            remappings=[
                ('map', '/map'),
                ('scan', 'scan'),
            ],
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_map',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'autostart': autostart,
                'node_names': ['map_server'],
            }],
            condition=IfCondition(start_map_server),
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            namespace=robot_namespace,
            name='lifecycle_manager_localization',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'autostart': autostart,
                'node_names': ['amcl'],
            }],
        ),
    ])
