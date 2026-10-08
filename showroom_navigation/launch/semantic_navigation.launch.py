#!/usr/bin/env python3
"""Launch semantic planning and the selected robots' Nav2 adapters."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Create the simulator-independent semantic navigation layer."""
    guide_autostart = LaunchConfiguration('guide_autostart')
    guide_startup_delay = LaunchConfiguration('guide_startup_delay')
    enable_robot_0 = LaunchConfiguration('enable_robot_0')
    enable_robot_1 = LaunchConfiguration('enable_robot_1')
    enable_route_visualization = LaunchConfiguration(
        'enable_route_visualization')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument('guide_autostart', default_value='false'),
        DeclareLaunchArgument('guide_startup_delay', default_value='3.0'),
        DeclareLaunchArgument('enable_robot_0', default_value='true'),
        DeclareLaunchArgument('enable_robot_1', default_value='false'),
        DeclareLaunchArgument(
            'enable_route_visualization', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        Node(
            package='showroom_navigation',
            executable='showroom_route_visualizer.py',
            name='showroom_route_visualizer',
            output='screen',
            condition=IfCondition(enable_route_visualization),
            parameters=[{'use_sim_time': use_sim_time}],
        ),
        Node(
            package='showroom_navigation',
            executable='showroom_navigation_gateway.py',
            name='showroom_navigation_gateway',
            output='screen',
            parameters=[{
                'backend': 'nav2',
                'use_sim_time': use_sim_time,
            }],
        ),
        Node(
            package='showroom_navigation',
            executable='showroom_nav2_adapter.py',
            namespace='robot_1',
            name='showroom_nav2_adapter',
            output='screen',
            condition=IfCondition(enable_robot_1),
            parameters=[{
                'robot_id': 'robot_1',
                'use_sim_time': use_sim_time,
            }],
        ),
        Node(
            package='showroom_navigation',
            executable='showroom_nav2_adapter.py',
            namespace='robot_0',
            name='showroom_nav2_adapter',
            output='screen',
            condition=IfCondition(enable_robot_0),
            parameters=[{
                'robot_id': 'robot_0',
                'use_sim_time': use_sim_time,
            }],
        ),
        Node(
            package='showroom_navigation',
            executable='showroom_default_mission.py',
            name='showroom_default_mission',
            output='screen',
            condition=IfCondition(enable_robot_0),
            parameters=[{
                'autostart': guide_autostart,
                'startup_delay_sec': guide_startup_delay,
                # Mission dispatch is a control-plane delay. Wall time lets it
                # start even when Gazebo is paused or /clock is not ready yet.
                'use_sim_time': False,
            }],
        ),
    ])
