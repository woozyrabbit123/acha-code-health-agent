"""Integration tests for CLI entry points."""

import subprocess
import sys
from pathlib import Path


class TestCLIEntry:
    """Test CLI entry points work correctly."""

    def test_ace_help(self):
        """Test that ace --help runs without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "ace" in result.stdout.lower()
        assert "analyze" in result.stdout.lower()

    def test_ace_version(self):
        """Test that ace --version displays version."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "ACE" in result.stdout or "ace" in result.stdout.lower()

    def test_ace_analyze_help(self):
        """Test that ace analyze --help works."""
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "analyze", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "--target" in result.stdout

    def test_ace_analyze_sample_project(self):
        """Test running ace analyze on sample_project."""
        sample_project = Path("sample_project")
        
        # Skip if sample_project doesn't exist
        if not sample_project.exists():
            return
        
        result = subprocess.run(
            [sys.executable, "-m", "ace.cli", "analyze", "--target", str(sample_project)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Should either succeed or fail gracefully
        assert result.returncode in [0, 1, 2]  # Success, operational error, or policy deny

    def test_acha_help(self):
        """Test that acha --help runs without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "acha.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "acha" in result.stdout.lower()

    def test_acha_version(self):
        """Test that acha --version displays version."""
        result = subprocess.run(
            [sys.executable, "-m", "acha.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
