#!/usr/bin/env python3
"""Short command-line launcher for the showroom profile entry point."""

import argparse
import os
import sys


PROFILES = {
    'manual': '主模式：语音控制 + 默认路线（说“开始”后自动导览，可随时下指令）',
    'qwen': '主模式 + 本地 Qwen 模型（Ollama，无需 Mock）',
    'demo': 'Gazebo 显示双机器人，自动开始完整导览并支持语音命令',
    'headless': '双机器人无界面运行',
    'mock': '无界面启动并启用 Mock LLM',
    'llm': '打开 RViz 并启用 Ollama',
    'voice': '打开 RViz、Ollama、Whisper 和 Piper',
    'navigation': '双机器人纯 Nav2 开发模式',
    'single': 'Gazebo 显示单导览机器人',
    'single_headless': '单导览机器人无界面运行',
}


def launch_command(profile):
    """Build the ros2 launch command for a named startup profile."""
    return [
        'ros2', 'launch', 'showroom_bringup', 'showroom.launch.py',
        f'profile:={profile}',
    ]


def create_parser():
    """Create the small user-facing command-line parser."""
    parser = argparse.ArgumentParser(
        prog='showroom',
        description='一条命令启动 Gazebo 展厅机器人系统')
    parser.add_argument(
        'profile', nargs='?', default='manual', choices=PROFILES,
        help='启动档位，默认为 manual')
    parser.add_argument(
        '--list', action='store_true',
        help='列出所有启动档位')
    parser.add_argument(
        '--dry-run', action='store_true',
        help='显示底层命令但不启动')
    return parser


def main():
    """Parse the requested profile and replace this process with ros2 launch."""
    arguments = create_parser().parse_args()
    if arguments.list:
        width = max(len(name) for name in PROFILES)
        for name, description in PROFILES.items():
            marker = '（默认）' if name == 'manual' else ''
            print(f'{name:<{width}}  {description}{marker}')
        return 0

    command = launch_command(arguments.profile)
    if arguments.dry_run:
        print(' '.join(command))
        return 0

    os.execvp(command[0], command)
    return 1


if __name__ == '__main__':
    sys.exit(main())
