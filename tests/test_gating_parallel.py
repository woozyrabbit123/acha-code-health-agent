"""Test parallel execution Pro gating.

Verifies that Community users get exit code 2 when attempting to use
parallel execution (--jobs > 1 or --max-workers > 1).
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def test_jobs_4_without_license_exits_2(tmp_path):
    """Community: analyze --jobs 4 should exit with code 2"""
    # Create a minimal test project
    test_project = tmp_path / "test_project"
    test_project.mkdir()
    (test_project / "test.py").write_text("print('hello')\n")

    # Run with --jobs 4 without Pro license
    # This should call require_pro() and exit with code 2
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "acha.cli",
            "analyze",
            "--target",
            str(test_project),
            "--jobs",
            "4",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
    assert "Pro" in result.stderr, "Error message should mention 'Pro'"
    assert "parallel" in result.stderr.lower() or "Parallel" in result.stderr, (
        "Error message should mention parallel scanning"
    )


def test_max_workers_4_without_license_exits_2(tmp_path):
    """Community: analyze --max-workers 4 should exit with code 2"""
    # Create a minimal test project
    test_project = tmp_path / "test_project"
    test_project.mkdir()
    (test_project / "test.py").write_text("print('hello')\n")

    # Run with --max-workers 4 without Pro license
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "acha.cli",
            "analyze",
            "--target",
            str(test_project),
            "--max-workers",
            "4",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
    assert "Pro" in result.stderr, "Error message should mention 'Pro'"
    assert "parallel" in result.stderr.lower() or "Parallel" in result.stderr, (
        "Error message should mention parallel scanning"
    )


def test_jobs_1_without_license_succeeds(tmp_path):
    """Community: analyze --jobs 1 should succeed (exit 0)"""
    # Create a minimal test project
    test_project = tmp_path / "test_project"
    test_project.mkdir()
    (test_project / "test.py").write_text("print('hello')\n")

    # Run with --jobs 1 without Pro license
    # This should work fine for Community users
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "acha.cli",
            "analyze",
            "--target",
            str(test_project),
            "--jobs",
            "1",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}\nStderr: {result.stderr}\nStdout: {result.stdout}"


def test_default_workers_without_license_succeeds(tmp_path):
    """Community: analyze without --jobs/--max-workers should succeed (uses default 1)"""
    # Create a minimal test project
    test_project = tmp_path / "test_project"
    test_project.mkdir()
    (test_project / "test.py").write_text("print('hello')\n")

    # Run without specifying workers (should default to 1 for Community)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "acha.cli",
            "analyze",
            "--target",
            str(test_project),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}\nStderr: {result.stderr}\nStdout: {result.stdout}"


@pytest.mark.skip(reason="Requires valid Pro license file or complex mocking to test")
def test_jobs_4_with_pro_license_succeeds(tmp_path):
    """Pro: analyze --jobs 4 with license should succeed (exit 0)

    NOTE: This test requires a valid license file in ~/.acha/license.json
    to test Pro features. For manual verification:
    1. Place valid license.json in ~/.acha/
    2. Run: acha analyze --target sample_project --jobs 4
    3. Verify: exit code 0
    """
    pytest.skip("Requires valid Pro license file")


@pytest.mark.skip(reason="Requires valid Pro license file or complex mocking to test")
def test_max_workers_4_with_pro_license_succeeds(tmp_path):
    """Pro: analyze --max-workers 4 with license should succeed (exit 0)

    NOTE: This test requires a valid license file in ~/.acha/license.json
    to test Pro features. For manual verification:
    1. Place valid license.json in ~/.acha/
    2. Run: acha analyze --target sample_project --max-workers 4
    3. Verify: exit code 0
    """
    pytest.skip("Requires valid Pro license file")
