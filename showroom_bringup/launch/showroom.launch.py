#!/usr/bin/env python3
"""Simple profile-based entry point for common showroom launches."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


PROFILE_CONFIGS = {
    'manual': {
        'launch': 'dual_robot.launch.py',
        'arguments': {
            'headless': 'false',
            'rviz': 'false',
            'enable_llm': 'true',
            'llm_backend': 'mock',
            'enable_voice': 'true',
        },
        'description': 'main mode: voice control plus the default route',
    },
    'demo': {
        'launch': 'dual_robot.launch.py',
        'arguments': {
            'headless': 'false',
            'rviz': 'false',
            'business_auto_start': 'true',
            'enable_llm': 'true',
            'llm_backend': 'mock',
            'enable_voice': 'true',
        },
        'description': 'automatic two-robot demonstration with local voice',
    },
    'qwen': {
        'launch': 'showroom_qwen.launch.py',
        'arguments': {},
        'description': 'main mode backed by the local Qwen model',
    },
    'headless': {
        'launch': 'dual_robot.launch.py',
        'arguments': {'headless': 'true', 'rviz': 'false'},
        'description': 'two robots without Gazebo or RViz windows',
    },
    'mock': {
        'launch': 'dual_robot.launch.py',
        'arguments': {
            'headless': 'true',
            'rviz': 'false',
            'enable_llm': 'true',
            'llm_backend': 'mock',
        },
        'description': 'natural-language integration without an external model',
    },
    'llm': {
        'launch': 'dual_robot.launch.py',
        'arguments': {
            'rviz': 'true',
            'enable_llm': 'true',
            'llm_backend': 'ollama',
        },
        'description': 'two robots with Ollama text interaction',
    },
    'voice': {
        'launch': 'dual_robot.launch.py',
        'arguments': {
            'rviz': 'true',
            'enable_llm': 'true',
            'llm_backend': 'ollama',
            'enable_voice': 'true',
        },
        'description': 'two robots with Ollama, Whisper and Piper',
    },
    'navigation': {
        'launch': 'dual_robot.launch.py',
        'arguments': {'business_mode': 'false', 'rviz': 'true'},
        'description': 'two-robot Nav2 development mode',
    },
    'single': {
        'launch': 'single_robot.launch.py',
        'arguments': {'headless': 'false', 'rviz': 'false'},
        'description': 'single guide robot in Gazebo',
    },
    'single_headless': {
        'launch': 'single_robot.launch.py',
        'arguments': {'headless': 'true', 'rviz': 'false'},
        'description': 'single guide robot without GUI windows',
    },
}


def launch_profile(context):
    """Resolve one named profile into an existing advanced launch file."""
    profile = LaunchConfiguration('profile').perform(context)
    configuration = PROFILE_CONFIGS[profile]
    launch_file = os.path.join(
        get_package_share_directory('showroom_bringup'),
        'launch', configuration['launch'])
    arguments = configuration['arguments']
    rendered = ' '.join(
        f'{name}:={value}' for name, value in arguments.items())
    return [
        LogInfo(msg=(
            f'Showroom profile: {profile} - '
            f'{configuration["description"]} [{rendered}]')),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(launch_file),
            launch_arguments=arguments.items(),
        ),
    ]


def generate_launch_description():
    """Expose one short profile argument for common startup scenarios."""
    return LaunchDescription([
        DeclareLaunchArgument(
            'profile',
            default_value='manual',
            choices=list(PROFILE_CONFIGS),
            description='Preconfigured startup mode'),
        OpaqueFunction(function=launch_profile),
    ])
