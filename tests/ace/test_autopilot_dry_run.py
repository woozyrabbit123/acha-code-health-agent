"""Test autopilot dry-run mode for stable, deterministic output."""

import tempfile
from pathlib import Path

from ace.autopilot import AutopilotConfig, run_autopilot
from ace.errors import ExitCode


def test_autopilot_dry_run_produces_plans():
    """Test that autopilot dry-run produces plans without mutations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a Python file with a fixable issue
        test_file = tmpdir / "test.py"
        test_file.write_text(
            """import requests

def fetch_data():
    response = requests.get("http://example.com")
    return response.json()
""",
            encoding="utf-8",
        )

        # Run autopilot in dry-run mode
        cfg = AutopilotConfig(
            target=tmpdir,
            allow_mode="suggest",
            dry_run=True,
            silent=True,
        )

        exit_code, stats = run_autopilot(cfg)

        # Should succeed
        assert exit_code == ExitCode.SUCCESS

        # Should find the issue
        assert stats.findings_count > 0

        # Should generate plans
        assert stats.plans_count > 0

        # Should approve plans
        assert stats.plans_approved > 0

        # Should NOT apply in dry-run mode
        assert stats.plans_applied == 0

        # Original file should be unchanged
        content = test_file.read_text(encoding="utf-8")
        assert "timeout" not in content


def test_autopilot_dry_run_stable_rerun():
    """Test that re-running autopilot dry-run produces identical output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a Python file with a fixable issue
        test_file = tmpdir / "test.py"
        test_file.write_text(
            """import requests

def fetch_data():
    response = requests.get("http://example.com")
    return response.json()
""",
            encoding="utf-8",
        )

        # Run 1
        cfg = AutopilotConfig(
            target=tmpdir,
            allow_mode="suggest",
            dry_run=True,
            silent=True,
        )

        exit_code1, stats1 = run_autopilot(cfg)

        # Run 2 (identical config)
        exit_code2, stats2 = run_autopilot(cfg)

        # Results should be identical
        assert exit_code1 == exit_code2
        assert stats1.findings_count == stats2.findings_count
        assert stats1.plans_count == stats2.plans_count
        assert stats1.plans_approved == stats2.plans_approved


def test_autopilot_dry_run_empty_directory():
    """Test autopilot dry-run on empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        cfg = AutopilotConfig(
            target=tmpdir,
            allow_mode="suggest",
            dry_run=True,
            silent=True,
        )

        exit_code, stats = run_autopilot(cfg)

        # Should succeed
        assert exit_code == ExitCode.SUCCESS

        # Should find no issues
        assert stats.findings_count == 0
        assert stats.plans_count == 0
