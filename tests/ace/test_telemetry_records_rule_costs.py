"""Test telemetry records rule execution costs."""

import json
import tempfile
from pathlib import Path

import pytest

from ace.telemetry import Telemetry, time_block


def test_telemetry_records_rule_costs():
    """Test that telemetry records rule execution times to JSONL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / ".ace" / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        # Record some rule executions
        telemetry.record("PY-S201-SUBPROCESS-CHECK", 10.5)
        telemetry.record("PY-S201-SUBPROCESS-CHECK", 12.3)
        telemetry.record("PY-E201-BROAD-EXCEPT", 5.2)

        # Verify JSONL file exists
        assert telemetry_path.exists()

        # Verify JSONL content
        with open(telemetry_path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 3

        # Parse first entry
        entry1 = json.loads(lines[0])
        assert entry1["rule_id"] == "PY-S201-SUBPROCESS-CHECK"
        assert entry1["duration_ms"] == 10.5
        assert "timestamp" in entry1

        # Load stats
        stats = telemetry.load_stats()
        assert stats.total_executions == 3
        assert "PY-S201-SUBPROCESS-CHECK" in stats.per_rule_avg_ms
        assert "PY-E201-BROAD-EXCEPT" in stats.per_rule_avg_ms

        # Check averages
        avg_subprocess = stats.per_rule_avg_ms["PY-S201-SUBPROCESS-CHECK"]
        assert abs(avg_subprocess - 11.4) < 0.01  # (10.5 + 12.3) / 2

        avg_except = stats.per_rule_avg_ms["PY-E201-BROAD-EXCEPT"]
        assert abs(avg_except - 5.2) < 0.01


def test_telemetry_time_block():
    """Test time_block context manager records timing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / ".ace" / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        # Use time_block context manager
        with time_block("TEST-RULE", telemetry):
            # Simulate some work
            sum(range(1000))

        # Verify telemetry was recorded
        assert telemetry_path.exists()

        stats = telemetry.load_stats()
        assert stats.total_executions == 1
        assert "TEST-RULE" in stats.per_rule_avg_ms
        # Duration should be > 0
        assert stats.per_rule_avg_ms["TEST-RULE"] > 0


def test_telemetry_get_top_slow_rules():
    """Test getting top slowest rules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / ".ace" / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        # Record rules with different speeds
        telemetry.record("FAST-RULE", 1.0)
        telemetry.record("SLOW-RULE", 100.0)
        telemetry.record("MEDIUM-RULE", 50.0)

        # Get top slow rules
        top_slow = telemetry.get_top_slow_rules(limit=2)

        assert len(top_slow) == 2
        # Should be sorted by avg_ms descending
        assert top_slow[0][0] == "SLOW-RULE"
        assert top_slow[0][1] == 100.0
        assert top_slow[1][0] == "MEDIUM-RULE"
        assert top_slow[1][1] == 50.0


def test_telemetry_empty():
    """Test telemetry with no data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / ".ace" / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        stats = telemetry.load_stats()
        assert stats.total_executions == 0
        assert len(stats.per_rule_avg_ms) == 0

        top_slow = telemetry.get_top_slow_rules()
        assert len(top_slow) == 0


def test_telemetry_clear():
    """Test clearing telemetry data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / ".ace" / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        # Record some data
        telemetry.record("TEST-RULE", 10.0)
        assert telemetry_path.exists()

        # Clear
        telemetry.clear()
        assert not telemetry_path.exists()

        # Stats should be empty
        stats = telemetry.load_stats()
        assert stats.total_executions == 0


def test_telemetry_handles_malformed_lines():
    """Test that telemetry gracefully handles malformed JSONL lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / ".ace" / "telemetry.jsonl"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)

        # Write some valid and invalid lines
        with open(telemetry_path, "w") as f:
            f.write('{"rule_id": "RULE1", "duration_ms": 10.0, "timestamp": 123}\n')
            f.write('invalid json line\n')
            f.write('{"rule_id": "RULE2", "duration_ms": 20.0, "timestamp": 456}\n')

        telemetry = Telemetry(telemetry_path=telemetry_path)
        stats = telemetry.load_stats()

        # Should only count valid entries
        assert stats.total_executions == 2
        assert "RULE1" in stats.per_rule_avg_ms
        assert "RULE2" in stats.per_rule_avg_ms
