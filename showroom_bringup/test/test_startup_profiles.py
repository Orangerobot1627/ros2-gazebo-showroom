#!/usr/bin/env python3
"""Validate that the simplified startup command and launch profiles agree."""

import contextlib
import importlib.util
import io
from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    """Load one project Python file without requiring package installation."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(starter, arguments):
    """Run the starter main function and capture its standard output."""
    previous = sys.argv
    output = io.StringIO()
    try:
        sys.argv = ['showroom', *arguments]
        with contextlib.redirect_stdout(output):
            result = starter.main()
    finally:
        sys.argv = previous
    return result, output.getvalue()


def main():
    """Check profile parity and user-facing command behavior."""
    launch = load_module(
        'showroom_launch', PACKAGE_ROOT / 'launch' / 'showroom.launch.py')
    starter = load_module(
        'showroom_start', PACKAGE_ROOT / 'scripts' / 'showroom_start.py')

    assert set(launch.PROFILE_CONFIGS) == set(starter.PROFILES)
    assert launch.PROFILE_CONFIGS['demo']['arguments'][
        'business_auto_start'] == 'true'
    assert launch.PROFILE_CONFIGS['manual']['arguments'] == {
        'headless': 'false',
        'rviz': 'false',
        'enable_llm': 'true',
        'llm_backend': 'mock',
        'enable_voice': 'true',
    }
    assert launch.PROFILE_CONFIGS['headless']['arguments'] == {
        'headless': 'true', 'rviz': 'false'}
    assert launch.PROFILE_CONFIGS['single']['launch'] == (
        'single_robot.launch.py')

    result, output = invoke(starter, ['--list'])
    assert result == 0
    assert all(profile in output for profile in starter.PROFILES)

    result, output = invoke(starter, ['headless', '--dry-run'])
    assert result == 0
    assert output.strip() == (
        'ros2 launch showroom_bringup showroom.launch.py profile:=headless')
    print('showroom startup profiles: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
