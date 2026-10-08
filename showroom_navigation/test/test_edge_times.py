#!/usr/bin/env python3
"""Deterministic tests for learned edge traversal times."""

from pathlib import Path
import sys
import tempfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from showroom_edge_times import EdgeTimeModel  # noqa: E402
from showroom_navigation import WeightedCostModel  # noqa: E402


def main():
    model = EdgeTimeModel(alpha=0.5)
    assert model.time_for('a->b') is None
    model.record('a->b', 10.0)
    assert model.time_for('a->b') == 10.0
    model.record('a->b', 20.0)  # EMA: 0.5 * 10 + 0.5 * 20
    assert abs(model.time_for('a->b') - 15.0) < 1e-9
    model.record('a->b', -1.0)  # ignored
    model.record('a->b', float('nan'))  # ignored
    model.record('a->b', 0.0)  # ignored
    assert abs(model.time_for('a->b') - 15.0) < 1e-9

    assert EdgeTimeModel(default_seconds=3.0).time_for('unknown') == 3.0

    # A large model refuses to guess and falls back to the default.
    big = EdgeTimeModel(default_seconds=2.0)
    for index in range(5):
        big.record(f'edge-{index}', 1.0)
    assert big.time_for('edge-0', sample_limit=3) == 2.0
    assert big.time_for('edge-0', sample_limit=100) == 1.0

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'edge_times.yaml'
        model.save(path)
        reloaded = EdgeTimeModel.load(path)
        assert abs(reloaded.time_for('a->b') - 15.0) < 1e-9
        assert yaml.safe_load(path.read_text(encoding='utf-8'))[
            'edges']['a->b'] == 15.0
        assert EdgeTimeModel.load(Path(temp) / 'missing.yaml').samples == {}
        (Path(temp) / 'broken.yaml').write_text('{{{', encoding='utf-8')
        assert EdgeTimeModel.load(Path(temp) / 'broken.yaml').samples == {}

    # A learned time adds to the edge cost only when the profile weights it.
    lookup = EdgeTimeModel(alpha=1.0)
    lookup.record('vision_hall_entry->vision_inside', 30.0)
    weighted = WeightedCostModel(
        distance_weight=1.0, time_weight=1.0, time_lookup=lookup.time_for)
    learned = weighted.edge_cost(
        10.0, {'edge_id': 'vision_hall_entry->vision_inside'})
    unknown = weighted.edge_cost(10.0, {'edge_id': 'other->edge'})
    assert learned == 40.0, learned
    assert unknown == 10.0, unknown

    # The learned profile keeps the distance cost when no time is known.
    plain = WeightedCostModel(distance_weight=1.0, time_weight=6.0,
                              time_lookup=None)
    assert plain.edge_cost(10.0, {'edge_id': 'x->y'}) == 10.0

    print('Learned edge traversal times: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
