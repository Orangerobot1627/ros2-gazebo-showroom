#!/usr/bin/env python3
"""
Learned per-edge traversal times for the semantic route graph.

This is the lightweight "auto-calibrate the weights" step: instead of setting a
travel-time cost by hand, the model records an exponential moving average of the
seconds actually spent traversing each directed graph edge and feeds that back
into the route cost. It mirrors the TimeMarker / TimeScorer pair in the Nav2
Route Server in a compact, dependency-free form.
"""

import math
from pathlib import Path

import yaml


class EdgeTimeModel:
    """Exponential-moving-average traversal time per directed graph edge."""

    def __init__(self, alpha=0.4, default_seconds=None, samples=None):
        if not 0.0 < float(alpha) <= 1.0:
            raise ValueError('alpha must be within (0, 1]')
        self.alpha = float(alpha)
        self.default_seconds = (
            None if default_seconds is None else float(default_seconds))
        self.samples = {
            str(edge_id): float(seconds)
            for edge_id, seconds in (samples or {}).items()
        }

    def record(self, edge_id, seconds):
        """Fold one observed traversal time into the edge's moving average."""
        seconds = float(seconds)
        if not math.isfinite(seconds) or seconds <= 0.0:
            return
        edge_id = str(edge_id)
        previous = self.samples.get(edge_id)
        if previous is None:
            self.samples[edge_id] = seconds
        else:
            self.samples[edge_id] = (
                (1.0 - self.alpha) * previous + self.alpha * seconds)

    def time_for(self, edge_id, sample_limit=200):
        """Return the learned time for an edge, or None when unknown."""
        if len(self.samples) > int(sample_limit):
            return self.default_seconds
        value = self.samples.get(str(edge_id))
        if value is None:
            return self.default_seconds
        return value

    def to_document(self):
        """Return a YAML/JSON-compatible snapshot."""
        return {
            'alpha': self.alpha,
            'default_seconds': self.default_seconds,
            'edges': dict(sorted(self.samples.items())),
        }

    @classmethod
    def from_document(cls, document):
        """Rebuild a model from a snapshot."""
        document = document or {}
        return cls(
            alpha=document.get('alpha', 0.4),
            default_seconds=document.get('default_seconds'),
            samples=document.get('edges') or {},
        )

    @classmethod
    def load(cls, path):
        """Load a model from YAML, or return an empty one when absent."""
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            document = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        except (OSError, yaml.YAMLError):
            return cls()
        return cls.from_document(document)

    def save(self, path):
        """Persist the model as YAML."""
        Path(path).write_text(
            yaml.safe_dump(self.to_document(), sort_keys=True),
            encoding='utf-8')
