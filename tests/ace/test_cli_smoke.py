"""Smoke tests for ACE CLI."""

import subprocess
import sys


def test_cli_help():
    """Test that ace --help exits 0 and shows subcommands."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"

    output = result.stdout

    # Check that all five subcommands are listed
    assert "analyze" in output, "Missing 'analyze' subcommand in help"
    assert "refactor" in output, "Missing 'refactor' subcommand in help"
    assert "validate" in output, "Missing 'validate' subcommand in help"
    assert "export" in output, "Missing 'export' subcommand in help"
    assert "apply" in output, "Missing 'apply' subcommand in help"


def test_cli_version():
    """Test that ace --version shows ACE v0.1.0-dev."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"

    output = result.stdout + result.stderr

    assert "ACE v0.1.0-dev" in output, f"Expected 'ACE v0.1.0-dev', got: {output}"


def test_analyze_stub():
    """Test that ace analyze prints stub message."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "analyze"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    assert "ACE v0.1 stub: analyze" in result.stdout


def test_refactor_stub():
    """Test that ace refactor prints stub message."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "refactor"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    assert "ACE v0.1 stub: refactor" in result.stdout


def test_validate_stub():
    """Test that ace validate prints stub message."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "validate"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    assert "ACE v0.1 stub: validate" in result.stdout


def test_export_stub():
    """Test that ace export prints stub message."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "export"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    assert "ACE v0.1 stub: export" in result.stdout


def test_apply_stub():
    """Test that ace apply prints stub message."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "apply"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    assert "ACE v0.1 stub: apply" in result.stdout
