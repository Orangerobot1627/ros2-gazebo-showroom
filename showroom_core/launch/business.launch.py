#!/usr/bin/env python3
"""Launch simulator-independent showroom business coordination."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Start the task manager and optional aggregate monitor."""
    auto_start = LaunchConfiguration('auto_start')
    auto_start_delay = LaunchConfiguration('auto_start_delay_sec')
    enable_monitor = LaunchConfiguration('enable_monitor')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument('auto_start', default_value='false'),
        DeclareLaunchArgument('auto_start_delay_sec', default_value='3.0'),
        DeclareLaunchArgument('enable_monitor', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        Node(
            package='showroom_core',
            executable='showroom_task_manager.py',
            name='showroom_task_manager',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'auto_start': auto_start,
                'auto_start_delay_sec': auto_start_delay,
                'navigation_backend': 'nav2',
            }],
        ),
        Node(
            package='showroom_core',
            executable='showroom_monitor.py',
            name='showroom_monitor',
            output='screen',
            condition=IfCondition(enable_monitor),
            parameters=[{'use_sim_time': use_sim_time}],
        ),
    ])
