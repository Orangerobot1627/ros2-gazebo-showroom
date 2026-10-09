#!/usr/bin/env python3
"""Launch the showroom world with the first guide robot."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Compose the world and single-robot spawn launch files."""
    simulation_share = get_package_share_directory('showroom_gz_sim')
    world_launch = os.path.join(
        simulation_share, 'launch', 'showroom_world.launch.py')
    spawn_launch = os.path.join(
        simulation_share, 'launch', 'spawn_robot.launch.py')
    bringup_share = get_package_share_directory('showroom_bringup')
    localization_launch = os.path.join(
        bringup_share, 'launch', 'localization.launch.py')
    navigation_launch = os.path.join(
        bringup_share, 'launch', 'navigation.launch.py')
    rviz_launch = os.path.join(
        bringup_share, 'launch', 'rviz.launch.py')
    semantic_navigation_share = get_package_share_directory(
        'showroom_navigation')
    semantic_navigation_launch = os.path.join(
        semantic_navigation_share, 'launch', 'semantic_navigation.launch.py')

    headless = LaunchConfiguration('headless')
    software_rendering = LaunchConfiguration('software_rendering')
    verbosity = LaunchConfiguration('verbosity')
    localization = LaunchConfiguration('localization')
    navigation = LaunchConfiguration('navigation')
    semantic_navigation = LaunchConfiguration('semantic_navigation')
    guide_autostart = LaunchConfiguration('guide_autostart')
    enable_pose_reset = LaunchConfiguration('enable_pose_reset')
    enable_route_visualization = LaunchConfiguration(
        'enable_route_visualization')
    safety_stop = LaunchConfiguration('safety_stop_enabled')
    safety_slowdown = LaunchConfiguration('safety_slowdown_enabled')
    enable_edge_learning = LaunchConfiguration('enable_edge_learning')
    edge_times_file = LaunchConfiguration('edge_times_file')
    rviz = LaunchConfiguration('rviz')
    enable_pedestrian = LaunchConfiguration('enable_pedestrian')

    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('software_rendering', default_value='true'),
        DeclareLaunchArgument('verbosity', default_value='2'),
        DeclareLaunchArgument(
            'localization',
            default_value='true',
            description='Start the map server and robot_0 AMCL localization'),
        DeclareLaunchArgument(
            'navigation',
            default_value='true',
            description='Start the robot_0 Nav2 navigation servers'),
        DeclareLaunchArgument(
            'semantic_navigation',
            default_value='true',
            description='Start semantic planning and the robot_0 Nav2 adapter'),
        DeclareLaunchArgument(
            'guide_autostart',
            default_value='false',
            description='Automatically start the accepted 65-waypoint tour'),
        DeclareLaunchArgument('enable_pose_reset', default_value='true'),
        DeclareLaunchArgument(
            'enable_route_visualization', default_value='true'),
        DeclareLaunchArgument(
            'safety_stop_enabled', default_value='true',
            description='Enable the collision monitor stop polygon'),
        DeclareLaunchArgument(
            'safety_slowdown_enabled', default_value='true',
            description='Enable the collision monitor slowdown polygon'),
        DeclareLaunchArgument(
            'enable_edge_learning', default_value='false',
            description='Record edge traversal times for route cost learning'),
        DeclareLaunchArgument(
            'edge_times_file', default_value='/tmp/showroom_edge_times.yaml'),
        DeclareLaunchArgument(
            'rviz',
            default_value='false',
            description='Open the Nav2 map, scan, costmap, and path view'),
        DeclareLaunchArgument(
            'enable_pedestrian', default_value='true',
            description='Walk the showroom pedestrian back and forth'),
        Node(
            package='showroom_gz_sim',
            executable='showroom_pedestrian.py',
            name='showroom_pedestrian',
            output='screen',
            parameters=[{'use_sim_time': True}],
            condition=IfCondition(enable_pedestrian),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(world_launch),
            launch_arguments={
                'headless': headless,
                'software_rendering': software_rendering,
                'verbosity': verbosity,
                'bridge_clock': 'true',
                'enable_pose_reset': enable_pose_reset,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(spawn_launch),
            launch_arguments={
                'namespace': 'robot_0',
                'robot_name': 'guide_robot',
                'x_pose': '0.0',
                'y_pose': '-14.5',
                'z_pose': '0.02',
                'yaw': '1.57079632679',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(localization_launch),
            condition=IfCondition(localization),
        ),
        TimerAction(
            period=4.0,
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(navigation_launch),
                    condition=IfCondition(navigation),
                    launch_arguments={
                        'safety_stop_enabled': safety_stop,
                        'safety_slowdown_enabled': safety_slowdown,
                    }.items(),
                ),
            ],
        ),
        TimerAction(
            period=7.0,
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(semantic_navigation_launch),
                    condition=IfCondition(semantic_navigation),
                    launch_arguments={
                        'guide_autostart': guide_autostart,
                        'enable_robot_0': 'true',
                        'enable_robot_1': 'false',
                        'enable_route_visualization': (
                            enable_route_visualization),
                        'enable_edge_learning': enable_edge_learning,
                        'edge_times_file': edge_times_file,
                        'use_sim_time': 'true',
                    }.items(),
                ),
            ],
        ),
        TimerAction(
            period=8.0,
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(rviz_launch),
                    condition=IfCondition(rviz),
                ),
            ],
        ),
    ])
