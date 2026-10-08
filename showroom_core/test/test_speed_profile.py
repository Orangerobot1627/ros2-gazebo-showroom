#!/usr/bin/env python3
"""Deterministic tests for the accelerate/decelerate velocity profiler."""

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    """Load the profiler module without starting a ROS node."""
    path = ROOT / 'scripts' / 'showroom_speed_profile.py'
    spec = importlib.util.spec_from_file_location('showroom_speed_profile', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def main():
    profiler_mod = load_module()
    SpeedProfiler = profiler_mod.SpeedProfiler

    # Linear acceleration ramps toward a higher target at linear_accel.
    ramp = SpeedProfiler(
        max_linear=0.5, max_angular=1.0,
        linear_accel=1.0, linear_decel=2.0,
        angular_accel=2.0, angular_decel=4.0,
        turn_slowdown_gain=0.6, min_turn_speed_scale=0.4)
    linear, angular = ramp.step(0.5, 0.0, 0.1)
    assert close(linear, 0.1), linear
    assert close(angular, 0.0), angular
    for _ in range(10):
        linear, angular = ramp.step(0.5, 0.0, 0.1)
    assert close(linear, 0.5), linear
    # A target above the limit is clamped, not overshot.
    linear, _ = ramp.step(5.0, 0.0, 1.0)
    assert close(linear, 0.5), linear

    # Deceleration uses linear_decel and can stop within one step.
    stopping = SpeedProfiler(max_linear=0.5, max_angular=1.0,
                             linear_accel=1.0, linear_decel=5.0)
    stopping.step(0.5, 0.0, 1.0)
    linear, _ = stopping.step(0.0, 0.0, 0.1)
    assert close(linear, 0.0), linear

    # Angular acceleration ramps independently of the linear command.
    turning = SpeedProfiler(max_linear=0.5, max_angular=1.0,
                            angular_accel=1.0, angular_decel=2.0,
                            turn_slowdown_gain=0.0)
    _, angular = turning.step(0.0, 1.0, 0.1)
    assert close(angular, 0.1), angular

    # A hard turn scales the forward speed down to the configured floor.
    corner = SpeedProfiler(max_linear=0.5, max_angular=1.0,
                           linear_accel=100.0, turn_slowdown_gain=0.6,
                           min_turn_speed_scale=0.4)
    assert close(corner.turn_scale(1.0), 0.4), corner.turn_scale(1.0)
    assert close(corner.turn_scale(0.0), 1.0), corner.turn_scale(0.0)
    linear, angular = corner.step(0.5, 1.0, 1.0)
    assert close(linear, 0.2, 1e-6), linear
    assert close(angular, 1.0, 1e-6), angular

    # reset returns the profiler to a full stop.
    corner.reset()
    assert corner.linear == 0.0 and corner.angular == 0.0

    for kwargs in (
            {'max_linear': 0.0},
            {'linear_accel': 0.0},
            {'turn_slowdown_gain': 1.5},
            {'min_turn_speed_scale': 0.0}):
        try:
            SpeedProfiler(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Invalid config accepted: {kwargs!r}')

    print('Speed profile accelerate/decelerate shaping: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
