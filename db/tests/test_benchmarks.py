"""Unit tests for Phase 5 benchmark suite (db.bench)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from db.bench.bench_latency import _percentile, compute_statistics
from db.bench.seed import _random_name, _random_string


def test_seed_random_helpers():
    """Verify seed random generation helpers."""
    s1 = _random_string(15)
    assert len(s1) == 15
    assert isinstance(s1, str)

    name = _random_name()
    assert " " in name
    parts = name.split(" ")
    assert len(parts) == 2
    assert len(parts[0]) > 0
    assert len(parts[1]) > 0


def test_latency_percentile_computation():
    """Verify percentile calculation logic."""
    data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50 = _percentile(data, 50.0)
    assert p50 == 55.0

    p0 = _percentile(data, 0.0)
    assert p0 == 10.0

    p100 = _percentile(data, 100.0)
    assert p100 == 100.0

    empty = _percentile([], 50.0)
    assert empty == 0.0


def test_latency_statistics_computation():
    """Verify compute_statistics generates all required statistical metrics."""
    samples = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    stats = compute_statistics(samples)

    assert stats["samples"] == 6
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 20.0
    assert stats["mean_ms"] == 15.0
    assert stats["p50_ms"] == 15.0
    assert stats["p95_ms"] > 18.0
    assert stats["p99_ms"] > 19.0
    assert stats["stddev_ms"] > 0.0

    empty_stats = compute_statistics([])
    assert empty_stats["samples"] == 0
    assert empty_stats["mean_ms"] == 0.0


def test_seed_cli_parser():
    """Verify seed script CLI arguments parsing."""
    from db.bench.seed import main
    with patch("sys.argv", ["argus-seed", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


def test_latency_cli_parser():
    """Verify bench_latency CLI arguments parsing."""
    from db.bench.bench_latency import main
    with patch("sys.argv", ["argus-bench-latency", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


def test_verify_cli_parser():
    """Verify bench_verify CLI arguments parsing."""
    from db.bench.bench_verify import main
    with patch("sys.argv", ["argus-bench-verify", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


def test_checkpoint_sweep_cli_parser():
    """Verify bench_checkpoint_sweep CLI arguments parsing."""
    from db.bench.bench_checkpoint_sweep import main
    with patch("sys.argv", ["argus-bench-checkpoint-sweep", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


def test_parallel_cli_parser():
    """Verify bench_parallel CLI arguments parsing."""
    from db.bench.bench_parallel import main
    with patch("sys.argv", ["argus-bench-parallel", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
