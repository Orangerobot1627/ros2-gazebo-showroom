#!/usr/bin/env python3
"""Primary Gazebo entry point for the technology showroom."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    package_share = get_package_share_directory('showroom_gz_sim')
    world_launch = os.path.join(
        package_share, 'launch', 'showroom_world.launch.py')
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(world_launch)),
    ])
