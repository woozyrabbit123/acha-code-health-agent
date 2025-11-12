"""Test telemetry write and read operations."""

import tempfile
from pathlib import Path

import pytest
from ace.telemetry import Telemetry, time_block


def test_telemetry_record_and_load():
    """Test recording and loading telemetry data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        # Record some timings
        telemetry.record("PY-S101-UNSAFE-HTTP", 10.5)
        telemetry.record("PY-E201-BROAD-EXCEPT", 20.3)
        telemetry.record("PY-S101-UNSAFE-HTTP", 12.1)  # Same rule, different time

        # Load stats
        stats = telemetry.load_stats()

        # Check averages
        assert "PY-S101-UNSAFE-HTTP" in stats.per_rule_avg_ms
        assert "PY-E201-BROAD-EXCEPT" in stats.per_rule_avg_ms

        # Average of 10.5 and 12.1 should be ~11.3
        assert abs(stats.per_rule_avg_ms["PY-S101-UNSAFE-HTTP"] - 11.3) < 0.1

        # Count should be 2 for PY-S101, 1 for PY-E201
        assert stats.per_rule_count["PY-S101-UNSAFE-HTTP"] == 2
        assert stats.per_rule_count["PY-E201-BROAD-EXCEPT"] == 1

        # Total executions should be 3
        assert stats.total_executions == 3


def test_time_block_context_manager():
    """Test time_block context manager records timing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        # Use time_block
        with time_block("TEST-RULE", telemetry):
            # Simulate some work
            pass

        # Load stats and verify
        stats = telemetry.load_stats()
        assert "TEST-RULE" in stats.per_rule_avg_ms
        assert stats.per_rule_count["TEST-RULE"] == 1
        # Duration should be small but > 0
        assert stats.per_rule_avg_ms["TEST-RULE"] >= 0


def test_get_top_slow_rules():
    """Test getting top slow rules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / "telemetry.jsonl"
        telemetry = Telemetry(telemetry_path=telemetry_path)

        # Record with varying times
        telemetry.record("FAST", 5.0)
        telemetry.record("MEDIUM", 50.0)
        telemetry.record("SLOW", 500.0)

        # Get top slow rules
        top_slow = telemetry.get_top_slow_rules(limit=2)

        # Should be sorted by avg_ms descending
        assert len(top_slow) == 2
        assert top_slow[0][0] == "SLOW"  # Rule ID
        assert top_slow[0][1] == 500.0  # Avg ms
        assert top_slow[1][0] == "MEDIUM"
        assert top_slow[1][1] == 50.0


def test_telemetry_persistence():
    """Test that telemetry persists across instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = Path(tmpdir) / "telemetry.jsonl"

        # Write with first instance
        telemetry1 = Telemetry(telemetry_path=telemetry_path)
        telemetry1.record("RULE-A", 100.0)

        # Read with second instance
        telemetry2 = Telemetry(telemetry_path=telemetry_path)
        stats = telemetry2.load_stats()

        assert "RULE-A" in stats.per_rule_avg_ms
        assert stats.per_rule_avg_ms["RULE-A"] == 100.0
