#!/usr/bin/env python3
"""Validate the interaction package wiring without external services."""

from pathlib import Path

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE = PACKAGE.parent


def main():
    launch_source = (
        PACKAGE / 'launch' / 'interaction.launch.py').read_text(
            encoding='utf-8')
    bridge_source = (
        PACKAGE / 'scripts' / 'showroom_llm_bridge.py').read_text(
            encoding='utf-8')
    interaction_plan = (
        PACKAGE / 'scripts' / 'showroom_plan.py').read_text(encoding='utf-8')
    core_plan = (
        WORKSPACE / 'showroom_core' / 'scripts' /
        'showroom_plan.py').read_text(encoding='utf-8')
    landmarks = yaml.safe_load(
        (PACKAGE / 'config' / 'landmarks.yaml').read_text(encoding='utf-8'))

    assert "DeclareLaunchArgument('enable_llm', default_value='false')" \
        in launch_source
    assert "DeclareLaunchArgument('enable_voice', default_value='false')" \
        in launch_source
    assert "package='showroom_interaction'" in launch_source
    assert "get_package_share_directory('showroom_interaction')" \
        in bridge_source
    assert landmarks['frame_id'] == 'map'
    assert interaction_plan == core_plan
    print('Interaction package, map knowledge, and launch contracts: OK')


if __name__ == '__main__':
    main()
