#!/usr/bin/env python3
"""
Main showroom mode backed by the local Qwen model instead of Mock.

Same behaviour as the default profile — say "开始" and the robot runs the
default itinerary while accepting higher-priority voice commands — but the
natural-language layer talks to a local Qwen model served by Ollama. There is
no online fallback: Qwen is treated as just another local component, so if the
model service is not up the LLM bridge simply reports it as unavailable.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """Compose the default dual-robot stack with the local Qwen backend."""
    bringup_share = get_package_share_directory('showroom_bringup')
    dual_robot = os.path.join(
        bringup_share, 'launch', 'dual_robot.launch.py')

    llm_endpoint = LaunchConfiguration('llm_endpoint')
    llm_model = LaunchConfiguration('llm_model')
    enable_voice = LaunchConfiguration('enable_voice')

    return LaunchDescription([
        DeclareLaunchArgument(
            'llm_endpoint', default_value='http://192.168.23.1:11434',
            description='Local Ollama/Qwen HTTP endpoint'),
        DeclareLaunchArgument(
            'llm_model', default_value='qwen3.5:4b',
            description='Local model name served by Ollama'),
        DeclareLaunchArgument('enable_voice', default_value='true'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(dual_robot),
            launch_arguments={
                'headless': 'false',
                'rviz': 'false',
                'enable_llm': 'true',
                'llm_backend': 'ollama',
                'llm_endpoint': llm_endpoint,
                'llm_model': llm_model,
                'enable_voice': enable_voice,
            }.items(),
        ),
    ])
