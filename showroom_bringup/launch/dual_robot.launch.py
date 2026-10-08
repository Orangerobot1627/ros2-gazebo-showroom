#!/usr/bin/env python3
"""Launch both showroom robots with independent AMCL and Nav2 stacks."""

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


def include(path, arguments=None, condition=None):
    """Return one included Python launch description."""
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(path),
        launch_arguments=(arguments or {}).items(),
        condition=condition,
    )


def generate_launch_description():
    """Compose world, two robots, localization, Nav2, and semantics."""
    simulation_share = get_package_share_directory('showroom_gz_sim')
    bringup_share = get_package_share_directory('showroom_bringup')
    navigation_share = get_package_share_directory('showroom_navigation')
    core_share = get_package_share_directory('showroom_core')
    interaction_share = get_package_share_directory('showroom_interaction')

    world_launch = os.path.join(
        simulation_share, 'launch', 'showroom_world.launch.py')
    spawn_launch = os.path.join(
        simulation_share, 'launch', 'spawn_robot.launch.py')
    localization_launch = os.path.join(
        bringup_share, 'launch', 'localization.launch.py')
    nav2_launch = os.path.join(
        bringup_share, 'launch', 'navigation.launch.py')
    semantic_launch = os.path.join(
        navigation_share, 'launch', 'semantic_navigation.launch.py')
    rviz_launch = os.path.join(
        bringup_share, 'launch', 'rviz.launch.py')
    business_launch = os.path.join(
        core_share, 'launch', 'business.launch.py')
    interaction_launch = os.path.join(
        interaction_share, 'launch', 'interaction.launch.py')
    robot_0_localization = os.path.join(
        bringup_share, 'config', 'robot_0_nav2.yaml')
    robot_1_localization = os.path.join(
        bringup_share, 'config', 'robot_1_nav2.yaml')
    robot_0_navigation = os.path.join(
        bringup_share, 'config', 'robot_0_navigation.yaml')
    robot_1_navigation = os.path.join(
        bringup_share, 'config', 'robot_1_navigation.yaml')

    headless = LaunchConfiguration('headless')
    software_rendering = LaunchConfiguration('software_rendering')
    verbosity = LaunchConfiguration('verbosity')
    guide_autostart = LaunchConfiguration('guide_autostart')
    business_mode = LaunchConfiguration('business_mode')
    business_auto_start = LaunchConfiguration('business_auto_start')
    enable_monitor = LaunchConfiguration('enable_monitor')
    enable_pose_reset = LaunchConfiguration('enable_pose_reset')
    enable_route_visualization = LaunchConfiguration(
        'enable_route_visualization')
    safety_stop = LaunchConfiguration('safety_stop_enabled')
    enable_edge_learning = LaunchConfiguration('enable_edge_learning')
    edge_times_file = LaunchConfiguration('edge_times_file')
    enable_llm = LaunchConfiguration('enable_llm')
    llm_backend = LaunchConfiguration('llm_backend')
    llm_endpoint = LaunchConfiguration('llm_endpoint')
    llm_model = LaunchConfiguration('llm_model')
    llm_request_timeout = LaunchConfiguration('llm_request_timeout_sec')
    enable_voice = LaunchConfiguration('enable_voice')
    voice_python_path = LaunchConfiguration('voice_python_path')
    voice_asr_model = LaunchConfiguration('voice_asr_model_path')
    voice_tts_model = LaunchConfiguration('voice_tts_model_path')
    voice_input_target = LaunchConfiguration('voice_input_target')
    voice_output_target = LaunchConfiguration('voice_output_target')
    voice_rms_threshold = LaunchConfiguration('voice_rms_threshold')
    rviz = LaunchConfiguration('rviz')

    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('software_rendering', default_value='true'),
        DeclareLaunchArgument('verbosity', default_value='2'),
        DeclareLaunchArgument('guide_autostart', default_value='false'),
        DeclareLaunchArgument('business_mode', default_value='true'),
        DeclareLaunchArgument('business_auto_start', default_value='false'),
        DeclareLaunchArgument('enable_monitor', default_value='true'),
        DeclareLaunchArgument('enable_pose_reset', default_value='true'),
        DeclareLaunchArgument(
            'enable_route_visualization', default_value='true'),
        DeclareLaunchArgument(
            'safety_stop_enabled', default_value='false',
            description='Enable the collision monitor stop polygon'),
        DeclareLaunchArgument(
            'enable_edge_learning', default_value='false',
            description='Record edge traversal times for route cost learning'),
        DeclareLaunchArgument(
            'edge_times_file', default_value='/tmp/showroom_edge_times.yaml'),
        DeclareLaunchArgument('enable_llm', default_value='false'),
        DeclareLaunchArgument('llm_backend', default_value='ollama'),
        DeclareLaunchArgument(
            'llm_endpoint', default_value='http://192.168.23.1:11434'),
        DeclareLaunchArgument('llm_model', default_value='qwen3.5:4b'),
        DeclareLaunchArgument(
            'llm_request_timeout_sec', default_value='30.0'),
        DeclareLaunchArgument('enable_voice', default_value='false'),
        DeclareLaunchArgument(
            'voice_python_path',
            default_value='/home/xxl/ros2_ws/.voice_python'),
        DeclareLaunchArgument(
            'voice_asr_model_path',
            default_value='/home/xxl/ros2_ws/models/faster-whisper-small'),
        DeclareLaunchArgument(
            'voice_tts_model_path',
            default_value=(
                '/home/xxl/ros2_ws/models/piper/'
                'zh_CN-huayan-medium.onnx')),
        DeclareLaunchArgument('voice_input_target', default_value=''),
        DeclareLaunchArgument('voice_output_target', default_value=''),
        DeclareLaunchArgument('voice_rms_threshold', default_value='250.0'),
        DeclareLaunchArgument('rviz', default_value='false'),
        include(world_launch, {
            'headless': headless,
            'software_rendering': software_rendering,
            'verbosity': verbosity,
            'bridge_clock': 'true',
            'enable_pose_reset': enable_pose_reset,
        }),
        include(spawn_launch, {
            'namespace': 'robot_0',
            'robot_name': 'guide_robot',
            'x_pose': '0.0',
            'y_pose': '-14.5',
            'z_pose': '0.02',
            'yaw': '1.57079632679',
            'body_color': '0.12 0.48 0.95 1',
        }),
        include(spawn_launch, {
            'namespace': 'robot_1',
            'robot_name': 'coffee_robot',
            'x_pose': '2.3',
            'y_pose': '-14.5',
            'z_pose': '0.02',
            'yaw': '1.57079632679',
            'body_color': '0.10 0.70 0.30 1',
        }),
        include(localization_launch, {
            'robot_namespace': 'robot_0',
            'params_file': robot_0_localization,
            'start_map_server': 'true',
        }),
        include(localization_launch, {
            'robot_namespace': 'robot_1',
            'params_file': robot_1_localization,
            'start_map_server': 'false',
        }),
        TimerAction(period=4.0, actions=[
            include(nav2_launch, {
                'robot_namespace': 'robot_0',
                'navigation_params_file': robot_0_navigation,
                'safety_stop_enabled': safety_stop,
            }),
            include(nav2_launch, {
                'robot_namespace': 'robot_1',
                'navigation_params_file': robot_1_navigation,
                'safety_stop_enabled': safety_stop,
            }),
        ]),
        TimerAction(period=7.0, actions=[
            include(semantic_launch, {
                'guide_autostart': guide_autostart,
                'enable_robot_0': 'true',
                'enable_robot_1': 'true',
                'enable_route_visualization': enable_route_visualization,
                'enable_edge_learning': enable_edge_learning,
                'edge_times_file': edge_times_file,
                'use_sim_time': 'true',
            }),
        ]),
        TimerAction(period=7.5, actions=[
            include(
                business_launch,
                {
                    'auto_start': business_auto_start,
                    'enable_monitor': enable_monitor,
                    'use_sim_time': 'true',
                },
                condition=IfCondition(business_mode),
            ),
        ]),
        TimerAction(period=8.0, actions=[
            include(interaction_launch, {
                'enable_llm': enable_llm,
                'llm_backend': llm_backend,
                'llm_endpoint': llm_endpoint,
                'llm_model': llm_model,
                'llm_request_timeout_sec': llm_request_timeout,
                'enable_voice': enable_voice,
                'voice_python_path': voice_python_path,
                'voice_asr_model_path': voice_asr_model,
                'voice_tts_model_path': voice_tts_model,
                'voice_input_target': voice_input_target,
                'voice_output_target': voice_output_target,
                'voice_rms_threshold': voice_rms_threshold,
                'use_sim_time': 'true',
            }),
            include(rviz_launch, condition=IfCondition(rviz)),
        ]),
    ])
