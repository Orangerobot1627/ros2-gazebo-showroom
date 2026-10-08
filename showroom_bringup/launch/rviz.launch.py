#!/usr/bin/env python3
"""Open the guide robot Nav2 visualization."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Start RViz in robot_0's namespace with the shared map TF frame."""
    bringup_share = get_package_share_directory('showroom_bringup')
    default_config = os.path.join(
        bringup_share, 'rviz', 'showroom.rviz')
    config = LaunchConfiguration('rviz_config')

    return LaunchDescription([
        DeclareLaunchArgument('rviz_config', default_value=default_config),
        Node(
            package='rviz2',
            executable='rviz2',
            namespace='robot_0',
            name='rviz2',
            output='screen',
            arguments=['-d', config],
            parameters=[{'use_sim_time': True}],
            # Gazebo needs software rendering in VMware, while RViz's map
            # shader works correctly with the VMware OpenGL driver.
            additional_env={'LIBGL_ALWAYS_SOFTWARE': '0'},
        ),
    ])
