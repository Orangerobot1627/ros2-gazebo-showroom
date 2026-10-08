#!/usr/bin/env python3
"""Spawn the first showroom guide robot and publish its ROS kinematic tree."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """Create the robot_state_publisher and Gazebo model spawner."""
    description_share = get_package_share_directory('showroom_description')
    urdf = os.path.join(
        description_share, 'urdf', 'showroom_robot.urdf.xacro')
    sdf = os.path.join(
        description_share, 'urdf', 'showroom_robot.gazebo.xacro')

    namespace = LaunchConfiguration('namespace')
    robot_name = LaunchConfiguration('robot_name')
    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')
    z_pose = LaunchConfiguration('z_pose')
    yaw = LaunchConfiguration('yaw')
    body_color = LaunchConfiguration('body_color')

    robot_description = ParameterValue(
        Command(['xacro ', urdf]), value_type=str)
    gazebo_description = Command([
        'xacro ', sdf,
        ' namespace:=', namespace,
        ' robot_name:=', robot_name,
        " body_color:='", body_color, "'",
    ])

    state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        namespace=namespace,
        name='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'frame_prefix': ParameterValue(
                [namespace, '/'], value_type=str),
            'use_sim_time': True,
        }],
        output='screen',
    )

    spawn = Node(
        package='ros_gz_sim',
        executable='create',
        namespace=namespace,
        name='spawn_guide_robot',
        arguments=[
            '-world', 'showroom',
            '-name', robot_name,
            '-allow_renaming', 'false',
            '-string', gazebo_description,
            '-x', x_pose,
            '-y', y_pose,
            '-z', z_pose,
            '-Y', yaw,
        ],
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'namespace', default_value='robot_0',
            description='ROS namespace and TF frame prefix.'),
        DeclareLaunchArgument(
            'robot_name', default_value='guide_robot',
            description='Unique Gazebo entity name.'),
        DeclareLaunchArgument('x_pose', default_value='0.0'),
        DeclareLaunchArgument('y_pose', default_value='-14.5'),
        DeclareLaunchArgument('z_pose', default_value='0.02'),
        DeclareLaunchArgument('yaw', default_value='1.57079632679'),
        DeclareLaunchArgument(
            'body_color', default_value='0.12 0.48 0.95 1',
            description='Gazebo RGBA body color.'),
        state_publisher,
        spawn,
    ])
