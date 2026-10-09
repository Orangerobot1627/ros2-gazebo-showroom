#!/usr/bin/env python3
"""Launch the Stage-derived technology showroom in Gazebo Harmonic."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory('showroom_gz_sim')
    ros_gz_share = get_package_share_directory('ros_gz_sim')
    world = os.path.join(package_share, 'worlds', 'showroom.sdf')
    bridge_config = os.path.join(
        package_share, 'config', 'ros_gz_bridge.yaml')
    gui_config = os.path.join(
        package_share, 'config', 'showroom_gui.config')
    gazebo_launch = os.path.join(ros_gz_share, 'launch', 'gz_sim.launch.py')

    headless = LaunchConfiguration('headless')
    verbosity = LaunchConfiguration('verbosity')
    world_file = LaunchConfiguration('world_file')
    bridge_clock = LaunchConfiguration('bridge_clock')
    enable_pose_reset = LaunchConfiguration('enable_pose_reset')
    software_rendering = LaunchConfiguration('software_rendering')

    gazebo_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gazebo_launch),
        launch_arguments={
            'gz_args': [
                '-r -v ', verbosity,
                ' --gui-config ', gui_config,
                ' ', world_file,
            ],
            'on_exit_shutdown': 'true',
        }.items(),
        condition=UnlessCondition(headless),
    )
    gazebo_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gazebo_launch),
        launch_arguments={
            'gz_args': ['-r -s -v ', verbosity, ' ', world_file],
            'on_exit_shutdown': 'true',
        }.items(),
        condition=IfCondition(headless),
    )

    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='showroom_ros_gz_bridge',
        parameters=[{
            'config_file': bridge_config,
            'use_sim_time': True,
        }],
        output='screen',
        condition=IfCondition(bridge_clock),
    )

    pose_reset = Node(
        package='showroom_gz_sim',
        executable='showroom_reset_pose.py',
        name='showroom_pose_reset',
        output='screen',
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(enable_pose_reset),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'headless', default_value='false',
            description='Run only the Gazebo server without its GUI.'),
        DeclareLaunchArgument(
            'world_file', default_value=world,
            description='World SDF to load. A higher <real_time_factor> runs '
                        'the headless acceptance soak faster than real time.'),
        DeclareLaunchArgument(
            'verbosity', default_value='2',
            description='Gazebo console verbosity from 0 to 4.'),
        DeclareLaunchArgument(
            'bridge_clock', default_value='true',
            description='Start the centralized Gazebo-to-ROS bridge.'),
        DeclareLaunchArgument(
            'enable_pose_reset', default_value='true',
            description='Expose the validated showroom pose-reset service.'),
        DeclareLaunchArgument(
            'software_rendering', default_value='true',
            description='Use Mesa software rendering to avoid VMware flicker.'),
        SetEnvironmentVariable(
            name='LIBGL_ALWAYS_SOFTWARE', value='1',
            condition=IfCondition(software_rendering)),
        SetEnvironmentVariable(
            name='GZ_PARTITION',
            value=[
                'showroom_domain_',
                EnvironmentVariable('ROS_DOMAIN_ID', default_value='0'),
            ]),
        gazebo_gui,
        gazebo_headless,
        ros_gz_bridge,
        pose_reset,
    ])
