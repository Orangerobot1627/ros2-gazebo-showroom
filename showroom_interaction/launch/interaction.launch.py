#!/usr/bin/env python3
"""Launch the optional text and voice interaction adapters."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """Create independently switchable LLM, ASR, and TTS nodes."""
    share = get_package_share_directory('showroom_interaction')
    knowledge_file = os.path.join(share, 'config', 'landmarks.yaml')

    enable_llm = LaunchConfiguration('enable_llm')
    llm_backend = LaunchConfiguration('llm_backend')
    llm_endpoint = LaunchConfiguration('llm_endpoint')
    llm_model = LaunchConfiguration('llm_model')
    llm_timeout = LaunchConfiguration('llm_request_timeout_sec')
    enable_voice = LaunchConfiguration('enable_voice')
    voice_python_path = LaunchConfiguration('voice_python_path')
    voice_asr_model = LaunchConfiguration('voice_asr_model_path')
    voice_tts_model = LaunchConfiguration('voice_tts_model_path')
    voice_input_target = LaunchConfiguration('voice_input_target')
    voice_output_target = LaunchConfiguration('voice_output_target')
    voice_rms_threshold = LaunchConfiguration('voice_rms_threshold')
    voice_end_silence_ms = LaunchConfiguration('voice_end_silence_ms')
    voice_adaptive_noise = LaunchConfiguration('voice_adaptive_noise')
    voice_wake_words = LaunchConfiguration('voice_wake_words')
    voice_duplicate_window_sec = LaunchConfiguration(
        'voice_duplicate_window_sec')
    use_sim_time = LaunchConfiguration('use_sim_time')
    voice_environment = {
        'PYTHONPATH': [
            voice_python_path, ':',
            EnvironmentVariable('PYTHONPATH', default_value=''),
        ],
    }

    return LaunchDescription([
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
        DeclareLaunchArgument('voice_rms_threshold', default_value='150.0'),
        DeclareLaunchArgument('voice_end_silence_ms', default_value='1200'),
        DeclareLaunchArgument('voice_adaptive_noise', default_value='false'),
        DeclareLaunchArgument(
            'voice_wake_words',
            default_value='开始导览 开始 你好机器人 未来科技展馆'),
        DeclareLaunchArgument(
            'voice_duplicate_window_sec', default_value='3.0'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        Node(
            package='showroom_interaction',
            executable='showroom_llm_bridge.py',
            name='showroom_llm_bridge',
            output='screen',
            condition=IfCondition(enable_llm),
            parameters=[{
                'use_sim_time': use_sim_time,
                'backend': llm_backend,
                'endpoint': llm_endpoint,
                'model': llm_model,
                'request_timeout_sec': llm_timeout,
                'knowledge_file': knowledge_file,
            }],
        ),
        Node(
            package='showroom_interaction',
            executable='showroom_asr.py',
            name='showroom_asr',
            output='screen',
            condition=IfCondition(enable_voice),
            additional_env=voice_environment,
            parameters=[{
                'use_sim_time': use_sim_time,
                'model_path': voice_asr_model,
                'input_target': ParameterValue(
                    voice_input_target, value_type=str),
                'rms_threshold': voice_rms_threshold,
                'end_silence_ms': ParameterValue(
                    voice_end_silence_ms, value_type=int),
                'adaptive_noise': ParameterValue(
                    voice_adaptive_noise, value_type=bool),
                'wake_words': ParameterValue(
                    voice_wake_words, value_type=str),
                'duplicate_window_sec': ParameterValue(
                    voice_duplicate_window_sec, value_type=float),
            }],
        ),
        Node(
            package='showroom_interaction',
            executable='showroom_tts.py',
            name='showroom_tts',
            output='screen',
            condition=IfCondition(enable_voice),
            additional_env=voice_environment,
            parameters=[{
                'use_sim_time': use_sim_time,
                'model_path': voice_tts_model,
                'output_target': ParameterValue(
                    voice_output_target, value_type=str),
            }],
        ),
    ])
