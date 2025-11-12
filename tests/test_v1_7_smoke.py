"""Smoke tests for ACE v1.7 features.

Tests basic functionality of Learning v2, Telemetry v2, Risk Heatmap, and TUI.
"""

import json
from pathlib import Path

import pytest


def test_learning_v2_basic():
    """Test Learning v2 basic functionality."""
    from ace.learn import LearningEngine

    learning = LearningEngine(learn_path=Path("/tmp/test_learn.json"))

    # Record some outcomes
    learning.record_outcome("TEST-RULE-1", "applied", file_path="test.py")
    learning.record_outcome("TEST-RULE-1", "applied", file_path="test.py")
    learning.record_outcome("TEST-RULE-1", "reverted", file_path="test.py")
    learning.record_outcome("TEST-RULE-1", "reverted", file_path="test.py")
    learning.record_outcome("TEST-RULE-1", "reverted", file_path="test.py")

    # Check auto-skiplist was triggered (3 consecutive reverts)
    assert learning.should_skip_file_for_rule("TEST-RULE-1", "test.py")

    # Check tuned threshold calculation
    for i in range(5):
        learning.record_outcome("TEST-RULE-2", "applied", file_path="other.py")

    threshold = learning.tuned_threshold("TEST-RULE-2")
    assert 0.60 <= threshold <= 0.85

    # Clean up
    Path("/tmp/test_learn.json").unlink(missing_ok=True)


def test_telemetry_v2_basic():
    """Test Telemetry v2 basic functionality."""
    from ace.telemetry import Telemetry

    telemetry = Telemetry(telemetry_path=Path("/tmp/test_telemetry.jsonl"))

    # Record some data
    telemetry.record("TEST-RULE-1", duration_ms=100.0, files=1, ok=True, reverted=False)
    telemetry.record("TEST-RULE-1", duration_ms=200.0, files=1, ok=True, reverted=False)
    telemetry.record("TEST-RULE-2", duration_ms=50.0, files=1, ok=True, reverted=True)

    # Get summary
    stats = telemetry.summary(days=7)

    assert stats.total_executions == 3
    assert "TEST-RULE-1" in stats.per_rule_avg_ms
    assert "TEST-RULE-1" in stats.per_rule_p95_ms
    assert stats.per_rule_count["TEST-RULE-1"] == 2

    # Clean up
    Path("/tmp/test_telemetry.jsonl").unlink(missing_ok=True)


def test_risk_heatmap_basic():
    """Test Risk Heatmap basic functionality."""
    from ace.report import calculate_file_risk, generate_risk_heatmap
    from ace.uir import UnifiedIssue, Severity

    # Create test findings
    findings = [
        UnifiedIssue(
            file="test.py",
            line=10,
            rule="TEST-RULE-1",
            severity=Severity.HIGH,
            message="Test",
            suggestion="",
            snippet="",
        ),
        UnifiedIssue(
            file="test.py",
            line=20,
            rule="TEST-RULE-2",
            severity=Severity.MEDIUM,
            message="Test",
            suggestion="",
            snippet="",
        ),
    ]

    # Calculate risk
    risk_map = generate_risk_heatmap(findings)

    assert "test.py" in risk_map
    assert 0.0 <= risk_map["test.py"] <= 1.0


def test_tui_imports():
    """Test that TUI modules can be imported."""
    try:
        from ace.tui.app import ACEDashboard

        # Just test that it imports without error
        assert ACEDashboard is not None
    except ImportError:
        pytest.skip("Textual not installed")


def test_cli_help_commands():
    """Test that new CLI commands are registered."""
    from ace.cli import main
    import sys
    from unittest.mock import patch

    # Test that the new commands are available (they should not error out with --help)
    for command in ["learn show", "telemetry summary", "ui", "report health --target ."]:
        with patch.object(sys, "argv", ["ace"] + command.split() + ["--help"]):
            try:
                exit_code = main()
                # --help should return 0 or cause SystemExit(0)
            except SystemExit as e:
                assert e.code == 0, f"Command '{command} --help' failed"


if __name__ == "__main__":
    # Run tests
    test_learning_v2_basic()
    print("✓ Learning v2 smoke test passed")

    test_telemetry_v2_basic()
    print("✓ Telemetry v2 smoke test passed")

    test_risk_heatmap_basic()
    print("✓ Risk Heatmap smoke test passed")

    test_tui_imports()
    print("✓ TUI imports smoke test passed")

    print("\n✓ All v1.7 smoke tests passed!")
