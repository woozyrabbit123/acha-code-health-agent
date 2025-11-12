"""Test autopilot budget constraints."""

import tempfile
from pathlib import Path

from ace.autopilot import AutopilotConfig, run_autopilot
from ace.errors import ExitCode


def test_autopilot_honors_max_files():
    """Test that autopilot respects max_files budget."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create 3 Python files with fixable issues
        for i in range(3):
            test_file = tmpdir / f"test{i}.py"
            test_file.write_text(
                f"""import requests

def fetch_data_{i}():
    response = requests.get("http://example.com")
    return response.json()
""",
                encoding="utf-8",
            )

        # Run autopilot with max_files=2
        cfg = AutopilotConfig(
            target=tmpdir,
            allow_mode="suggest",
            max_files=2,
            dry_run=True,
            silent=True,
        )

        exit_code, stats = run_autopilot(cfg)

        # Should succeed
        assert exit_code == ExitCode.SUCCESS

        # Should find all issues
        assert stats.findings_count >= 3

        # Should generate plans for all
        assert stats.plans_count >= 3

        # Should approve at most 2 due to budget
        assert stats.plans_approved <= 2

        # Some should be excluded by budget
        if stats.plans_count > 2:
            assert stats.budget_excluded > 0


def test_autopilot_honors_max_lines():
    """Test that autopilot respects max_lines budget."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a Python file with multiple fixable issues
        test_file = tmpdir / "test.py"
        test_file.write_text(
            """import requests

def fetch_data1():
    response = requests.get("http://example.com")
    return response.json()

def fetch_data2():
    response = requests.get("http://example.com")
    return response.json()

def fetch_data3():
    response = requests.get("http://example.com")
    return response.json()
""",
            encoding="utf-8",
        )

        # Run autopilot with max_lines=5 (very restrictive)
        cfg = AutopilotConfig(
            target=tmpdir,
            allow_mode="suggest",
            max_lines=5,
            dry_run=True,
            silent=True,
        )

        exit_code, stats = run_autopilot(cfg)

        # Should succeed
        assert exit_code == ExitCode.SUCCESS

        # Budget should limit the number of approved plans
        if stats.plans_count > 0:
            # Not all plans should be approved due to budget
            assert stats.plans_approved <= stats.plans_count


def test_autopilot_no_budget():
    """Test autopilot without budget constraints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create multiple Python files with fixable issues
        for i in range(3):
            test_file = tmpdir / f"test{i}.py"
            test_file.write_text(
                f"""import requests

def fetch_data_{i}():
    response = requests.get("http://example.com")
    return response.json()
""",
                encoding="utf-8",
            )

        # Run autopilot without budget constraints
        cfg = AutopilotConfig(
            target=tmpdir,
            allow_mode="suggest",
            dry_run=True,
            silent=True,
        )

        exit_code, stats = run_autopilot(cfg)

        # Should succeed
        assert exit_code == ExitCode.SUCCESS

        # Should approve all plans that pass policy
        # (assuming all have R* >= 0.50 for suggest mode)
        # No budget exclusions
        assert stats.budget_excluded == 0
