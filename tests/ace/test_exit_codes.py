"""Tests for CLI exit code contract."""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ace.errors import ExitCode


class TestAnalyzeExitCodes:
    """Test exit codes for ace analyze command."""

    def test_analyze_success_empty_dir(self):
        """Test analyze returns 0 for successful analysis of empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, "-m", "ace.cli", "analyze", "--target", tmpdir],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == ExitCode.SUCCESS
            assert result.stdout.strip() == "[]"

    def test_analyze_success_with_findings(self):
        """Test analyze returns 0 even when findings are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Python file with bare except
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "ace.cli", "analyze", "--target", str(test_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == ExitCode.SUCCESS
            assert "PY-E201-BROAD-EXCEPT" in result.stdout

    def test_analyze_operational_error_missing_target(self):
        """Test analyze returns 1 for nonexistent target path."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "analyze", "--target", "/nonexistent/path"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.OPERATIONAL_ERROR
        assert "does not exist" in result.stderr

    def test_analyze_invalid_args_missing_target(self):
        """Test analyze returns 3 when --target is missing."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "analyze"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.INVALID_ARGS
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


class TestRefactorExitCodes:
    """Test exit codes for ace refactor command."""

    def test_refactor_success_empty_dir(self):
        """Test refactor returns 0 for empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, "-m", "ace.cli", "refactor", "--target", tmpdir],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == ExitCode.SUCCESS
            assert result.stdout.strip() == "[]"

    def test_refactor_success_with_plans(self):
        """Test refactor returns 0 when plans are generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "ace.cli", "refactor", "--target", str(test_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == ExitCode.SUCCESS
            assert "edits" in result.stdout

    def test_refactor_operational_error_missing_target(self):
        """Test refactor returns 1 for nonexistent target."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "refactor", "--target", "/nonexistent/path"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.OPERATIONAL_ERROR
        assert "does not exist" in result.stderr

    def test_refactor_invalid_args_missing_target(self):
        """Test refactor returns 3 when --target is missing."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "refactor"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.INVALID_ARGS


class TestValidateExitCodes:
    """Test exit codes for ace validate command."""

    def test_validate_success(self):
        """Test validate returns 0 for successful validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "ace.cli", "validate", "--target", str(test_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == ExitCode.SUCCESS

    def test_validate_operational_error_missing_target(self):
        """Test validate returns 1 for nonexistent target."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "validate", "--target", "/nonexistent/path"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.OPERATIONAL_ERROR
        assert "does not exist" in result.stderr

    def test_validate_invalid_args_missing_target(self):
        """Test validate returns 3 when --target is missing."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "validate"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.INVALID_ARGS


class TestApplyExitCodes:
    """Test exit codes for ace apply command."""

    def test_apply_success_no_changes(self):
        """Test apply returns 0 when no changes needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "ace.cli", "apply", "--target", str(test_file), "--yes"],
                capture_output=True,
                text=True,
                check=False,
            )
            # Should succeed with no changes
            assert result.returncode == ExitCode.SUCCESS

    def test_apply_operational_error_missing_target(self):
        """Test apply returns 1 for nonexistent target."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "apply", "--target", "/nonexistent/path", "--yes"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.OPERATIONAL_ERROR
        assert "does not exist" in result.stderr

    def test_apply_invalid_args_missing_target(self):
        """Test apply returns 3 when --target is missing."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "apply", "--yes"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.INVALID_ARGS


class TestExportExitCodes:
    """Test exit codes for ace export command."""

    def test_export_success(self):
        """Test export returns 0 (stub implementation)."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "export"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.SUCCESS
        assert "stub" in result.stdout.lower()


class TestGlobalExitCodes:
    """Test global CLI exit code behaviors."""

    def test_no_command_invalid_args(self):
        """Test running ace with no command returns 3."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.INVALID_ARGS
        assert "usage" in result.stdout.lower() or "usage" in result.stderr.lower()

    def test_help_returns_success(self):
        """Test --help returns 0."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.SUCCESS
        assert "usage" in result.stdout.lower()

    def test_version_returns_success(self):
        """Test --version returns 0."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.SUCCESS
        assert "ACE" in result.stdout or "ace" in result.stdout.lower()

    def test_unknown_command_invalid_args(self):
        """Test unknown command returns 3."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "unknown"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.INVALID_ARGS
        assert "invalid" in result.stderr.lower() or "unrecognized" in result.stderr.lower()


class TestVerboseErrorOutput:
    """Test --verbose flag for detailed error output."""

    def test_verbose_error_includes_details(self):
        """Test --verbose provides more error details."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ace.cli",
                "--verbose",
                "analyze",
                "--target",
                "/nonexistent/path",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == ExitCode.OPERATIONAL_ERROR
        # Should have error message
        assert len(result.stderr) > 0
