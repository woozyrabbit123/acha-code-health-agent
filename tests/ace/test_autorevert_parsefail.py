"""Tests for auto-revert on parse-fail functionality."""

import tempfile
from pathlib import Path

from ace.safety import atomic_write, parse_after_edit_ok


def test_parse_after_edit_ok_valid_python():
    """Test parse check passes for valid Python."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 + 2\n")

        result = parse_after_edit_ok(test_file)

        assert result is True


def test_parse_after_edit_ok_invalid_python():
    """Test parse check fails for invalid Python."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 +\n")  # Syntax error

        result = parse_after_edit_ok(test_file)

        assert result is False


def test_parse_after_edit_ok_missing_file():
    """Test parse check fails for missing file."""
    test_file = Path("/nonexistent/file.py")

    result = parse_after_edit_ok(test_file)

    assert result is False


def test_parse_after_edit_ok_non_python():
    """Test parse check assumes valid for non-Python files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("any content")

        result = parse_after_edit_ok(test_file)

        # Unknown file types are assumed valid
        assert result is True


def test_atomic_write_creates_file():
    """Test atomic write creates file correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        content = b"x = 1 + 2"

        atomic_write(test_file, content)

        assert test_file.exists()
        assert test_file.read_bytes() == content


def test_atomic_write_overwrites_file():
    """Test atomic write overwrites existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"

        # Write initial content
        test_file.write_text("old content")

        # Overwrite with atomic write
        new_content = b"new content"
        atomic_write(test_file, new_content)

        assert test_file.read_bytes() == new_content


def test_atomic_write_creates_parent_dirs():
    """Test atomic write creates parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "subdir" / "test.py"
        content = b"x = 1 + 2"

        atomic_write(test_file, content)

        assert test_file.exists()
        assert test_file.read_bytes() == content


def test_auto_revert_workflow():
    """Test complete auto-revert workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"

        # Start with valid content
        original_content = b"x = 1 + 2"
        atomic_write(test_file, original_content)
        assert parse_after_edit_ok(test_file) is True

        # Write invalid content
        invalid_content = b"x = 1 +"
        atomic_write(test_file, invalid_content)
        assert parse_after_edit_ok(test_file) is False

        # Revert to original
        atomic_write(test_file, original_content)
        assert parse_after_edit_ok(test_file) is True
        assert test_file.read_bytes() == original_content


def test_parse_after_edit_ok_markdown():
    """Test parse check for markdown files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "README.md"
        test_file.write_text("# Heading\n\nContent here.\n")

        result = parse_after_edit_ok(test_file)

        # Markdown files are assumed valid
        assert result is True


def test_parse_after_edit_ok_yaml():
    """Test parse check for YAML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "config.yml"
        test_file.write_text("key: value\n")

        result = parse_after_edit_ok(test_file)

        # YAML files are assumed valid (no validation yet)
        assert result is True


def test_parse_after_edit_ok_shell():
    """Test parse check for shell files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "script.sh"
        test_file.write_text("#!/bin/bash\necho 'hello'\n")

        result = parse_after_edit_ok(test_file)

        # Shell files are assumed valid (no validation yet)
        assert result is True
