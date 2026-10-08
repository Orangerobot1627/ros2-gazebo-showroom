#!/usr/bin/env python3
"""Start the guide robot's namespaced Nav2 navigation servers."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from launch_ros.parameter_descriptions import ParameterValue
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    """Create an isolated Nav2 stack that shares the global map and TF tree."""
    bringup_share = get_package_share_directory('showroom_bringup')
    navigator_share = get_package_share_directory('nav2_bt_navigator')
    default_params = os.path.join(
        bringup_share, 'config', 'robot_0_navigation.yaml')
    navigate_to_pose_tree = os.path.join(
        navigator_share,
        'behavior_trees',
        'navigate_w_replanning_only_if_path_becomes_invalid.xml',
    )

    namespace = LaunchConfiguration('robot_namespace')
    params_file = LaunchConfiguration('navigation_params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    safety_stop_enabled = LaunchConfiguration('safety_stop_enabled')

    configured_params = ParameterFile(
        RewrittenYaml(
            source_file=params_file,
            root_key=namespace,
            param_rewrites={
                'use_sim_time': use_sim_time,
                'autostart': autostart,
                'default_nav_to_pose_bt_xml': navigate_to_pose_tree,
            },
            convert_types=True,
        ),
        allow_substs=True,
    )

    lifecycle_nodes = [
        'controller_server',
        'smoother_server',
        'planner_server',
        'behavior_server',
        'velocity_smoother',
        'collision_monitor',
        'bt_navigator',
    ]

    common = {
        'namespace': namespace,
        'output': 'screen',
        'parameters': [configured_params],
    }

    return LaunchDescription([
        SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'),
        DeclareLaunchArgument('robot_namespace', default_value='robot_0'),
        DeclareLaunchArgument(
            'navigation_params_file', default_value=default_params),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('autostart', default_value='true'),
        DeclareLaunchArgument(
            'safety_stop_enabled', default_value='false',
            description='Enable the collision monitor stop polygon'),
        Node(
            package='nav2_controller',
            executable='controller_server',
            name='controller_server',
            remappings=[('cmd_vel', 'cmd_vel_nav')],
            **common,
        ),
        Node(
            package='nav2_smoother',
            executable='smoother_server',
            name='smoother_server',
            **common,
        ),
        Node(
            package='nav2_planner',
            executable='planner_server',
            name='planner_server',
            **common,
        ),
        Node(
            package='nav2_behaviors',
            executable='behavior_server',
            name='behavior_server',
            remappings=[('cmd_vel', 'cmd_vel_nav')],
            **common,
        ),
        Node(
            package='nav2_velocity_smoother',
            executable='velocity_smoother',
            name='velocity_smoother',
            remappings=[
                ('cmd_vel', 'cmd_vel_nav'),
                ('cmd_vel_smoothed', 'cmd_vel_smoothed'),
            ],
            **common,
        ),
        Node(
            package='nav2_collision_monitor',
            executable='collision_monitor',
            name='collision_monitor',
            namespace=namespace,
            output='screen',
            parameters=[
                configured_params,
                {'SafetyStop.enabled': ParameterValue(
                    safety_stop_enabled, value_type=bool)},
            ],
        ),
        Node(
            package='nav2_bt_navigator',
            executable='bt_navigator',
            name='bt_navigator',
            **common,
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            namespace=namespace,
            name='lifecycle_manager_navigation',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'autostart': autostart,
                'node_names': lifecycle_nodes,
            }],
        ),
    ])
