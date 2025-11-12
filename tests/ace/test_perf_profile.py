"""Tests for ACE performance profiling."""

import json
import tempfile
from pathlib import Path

from ace.perf import PerformanceProfiler, PhaseTimer, RuleTimer, get_profiler, reset_profiler


def test_phase_timer():
    """Test PhaseTimer basic functionality."""
    timer = PhaseTimer("test_phase")
    assert timer.name == "test_phase"
    assert timer.duration_ms is None

    duration = timer.stop()
    assert duration >= 0
    assert timer.duration_ms == duration
    assert timer.end_time is not None


def test_phase_timer_to_dict():
    """Test PhaseTimer serialization."""
    timer = PhaseTimer("analyze")
    timer.stop()

    data = timer.to_dict()
    assert data["phase"] == "analyze"
    assert "duration_ms" in data
    assert data["duration_ms"] >= 0


def test_rule_timer():
    """Test RuleTimer basic functionality."""
    timer = RuleTimer("PY-TEST-01")
    assert timer.rule_id == "PY-TEST-01"
    assert timer.file_count == 0
    assert timer.total_duration_ms == 0

    timer.add_duration(100)
    assert timer.file_count == 1
    assert timer.total_duration_ms == 100

    timer.add_duration(50)
    assert timer.file_count == 2
    assert timer.total_duration_ms == 150


def test_rule_timer_to_dict():
    """Test RuleTimer serialization."""
    timer = RuleTimer("PY-TEST-01")
    timer.add_duration(100)
    timer.add_duration(200)

    data = timer.to_dict()
    assert data["rule"] == "PY-TEST-01"
    assert data["file_count"] == 2
    assert data["total_duration_ms"] == 300
    assert data["avg_duration_ms"] == 150


def test_profiler_disabled_by_default():
    """Test that profiler is disabled by default."""
    reset_profiler()
    profiler = get_profiler()
    assert profiler.enabled is False

    # Operations should be no-ops when disabled
    profiler.start_phase("test")
    profiler.stop_phase("test")
    profiler.record_rule("RULE-1", 100)

    data = profiler.to_dict()
    assert len(data["phases"]) == 0
    assert len(data["rules"]) == 0


def test_profiler_enable():
    """Test enabling profiler."""
    reset_profiler()
    profiler = get_profiler()
    profiler.enable()
    assert profiler.enabled is True


def test_profiler_phase_tracking():
    """Test phase tracking in profiler."""
    reset_profiler()
    profiler = get_profiler()
    profiler.enable()

    # Start and stop phases
    profiler.start_phase("analyze")
    profiler.stop_phase("analyze")

    profiler.start_phase("refactor")
    profiler.stop_phase("refactor")

    data = profiler.to_dict()
    assert len(data["phases"]) == 2
    phase_names = {p["phase"] for p in data["phases"]}
    assert "analyze" in phase_names
    assert "refactor" in phase_names


def test_profiler_rule_tracking():
    """Test rule tracking in profiler."""
    reset_profiler()
    profiler = get_profiler()
    profiler.enable()

    # Record rule executions
    profiler.record_rule("PY-S101-UNSAFE-HTTP", 50)
    profiler.record_rule("PY-E201-BROAD-EXCEPT", 30)
    profiler.record_rule("PY-S101-UNSAFE-HTTP", 70)  # Same rule again

    data = profiler.to_dict()
    assert len(data["rules"]) == 2

    # Find PY-S101 rule
    py_s101 = next(r for r in data["rules"] if r["rule"] == "PY-S101-UNSAFE-HTTP")
    assert py_s101["file_count"] == 2
    assert py_s101["total_duration_ms"] == 120


def test_profiler_to_dict_sorted():
    """Test that profiler output is deterministically sorted."""
    reset_profiler()
    profiler = get_profiler()
    profiler.enable()

    # Add phases in non-alphabetical order
    profiler.start_phase("validate")
    profiler.stop_phase("validate")
    profiler.start_phase("analyze")
    profiler.stop_phase("analyze")
    profiler.start_phase("refactor")
    profiler.stop_phase("refactor")

    # Add rules with varying durations
    profiler.record_rule("RULE-A", 50)
    profiler.record_rule("RULE-C", 200)
    profiler.record_rule("RULE-B", 100)

    data = profiler.to_dict()

    # Phases should be sorted alphabetically
    phase_names = [p["phase"] for p in data["phases"]]
    assert phase_names == sorted(phase_names)

    # Rules should be sorted by total duration (descending)
    rule_durations = [r["total_duration_ms"] for r in data["rules"]]
    assert rule_durations == sorted(rule_durations, reverse=True)


def test_profiler_save():
    """Test saving profiler output to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reset_profiler()
        profiler = get_profiler()
        profiler.enable()

        profiler.start_phase("analyze")
        profiler.stop_phase("analyze")
        profiler.record_rule("TEST-RULE", 100)

        output_path = Path(tmpdir) / "profile.json"
        profiler.save(output_path)

        assert output_path.exists()

        # Load and verify JSON
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "phases" in data
        assert "rules" in data
        assert "total_duration_ms" in data
        assert len(data["phases"]) == 1
        assert len(data["rules"]) == 1


def test_profiler_total_duration():
    """Test that total duration is sum of phases."""
    reset_profiler()
    profiler = get_profiler()
    profiler.enable()

    profiler.start_phase("phase1")
    profiler.stop_phase("phase1")

    profiler.start_phase("phase2")
    profiler.stop_phase("phase2")

    data = profiler.to_dict()

    expected_total = sum(p["duration_ms"] for p in data["phases"])
    assert data["total_duration_ms"] == expected_total


def test_profiler_json_deterministic():
    """Test that profiler JSON output is deterministic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create profile 1
        reset_profiler()
        profiler1 = get_profiler()
        profiler1.enable()
        profiler1.start_phase("analyze")
        profiler1.stop_phase("analyze")
        profiler1.record_rule("RULE-1", 100)

        output1 = Path(tmpdir) / "profile1.json"
        profiler1.save(output1)

        # Create profile 2 (same operations)
        reset_profiler()
        profiler2 = get_profiler()
        profiler2.enable()
        profiler2.start_phase("analyze")
        profiler2.stop_phase("analyze")
        profiler2.record_rule("RULE-1", 100)

        output2 = Path(tmpdir) / "profile2.json"
        profiler2.save(output2)

        # Load both
        with open(output1, encoding="utf-8") as f:
            data1 = json.load(f)
        with open(output2, encoding="utf-8") as f:
            data2 = json.load(f)

        # Structure should be identical (durations may vary slightly)
        assert data1.keys() == data2.keys()
        assert len(data1["phases"]) == len(data2["phases"])
        assert len(data1["rules"]) == len(data2["rules"])

        # Rules should be identical
        assert data1["rules"] == data2["rules"]


def test_profiler_singleton():
    """Test that get_profiler returns singleton."""
    reset_profiler()
    profiler1 = get_profiler()
    profiler2 = get_profiler()

    assert profiler1 is profiler2


def test_profiler_reset():
    """Test resetting profiler."""
    reset_profiler()
    profiler1 = get_profiler()
    profiler1.enable()
    profiler1.start_phase("test")

    reset_profiler()
    profiler2 = get_profiler()

    # Should be a new instance
    assert profiler1 is not profiler2
    assert profiler2.enabled is False
