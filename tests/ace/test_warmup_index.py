"""Test content index warmup."""

import tempfile
from pathlib import Path

from ace.index import warmup_index


def test_warmup_index_empty_directory():
    """Test warmup_index on empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        stats = warmup_index(tmpdir)

        # Should succeed with 0 files indexed
        assert stats["indexed"] == 0
        assert stats["errors"] == 0


def test_warmup_index_single_file():
    """Test warmup_index on single file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a test file
        test_file = tmpdir / "test.py"
        test_file.write_text("x = 1", encoding="utf-8")

        stats = warmup_index(tmpdir)

        # Should index the file
        assert stats["indexed"] == 1
        assert stats["errors"] == 0

        # Should create .ace/index.json
        index_file = tmpdir / ".ace" / "index.json"
        assert index_file.exists()


def test_warmup_index_multiple_files():
    """Test warmup_index on multiple files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create multiple test files
        for i in range(5):
            test_file = tmpdir / f"test{i}.py"
            test_file.write_text(f"x{i} = {i}", encoding="utf-8")

        stats = warmup_index(tmpdir)

        # Should index all files
        assert stats["indexed"] == 5
        assert stats["errors"] == 0


def test_warmup_index_skips_binary_files():
    """Test that warmup_index skips binary files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create text and binary files
        text_file = tmpdir / "test.py"
        text_file.write_text("x = 1", encoding="utf-8")

        binary_file = tmpdir / "test.pyc"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        stats = warmup_index(tmpdir)

        # Should only index text file, skip binary
        assert stats["indexed"] == 1
        assert stats["errors"] == 0


def test_warmup_index_skips_hidden_files():
    """Test that warmup_index skips hidden files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create visible and hidden files
        visible_file = tmpdir / "test.py"
        visible_file.write_text("x = 1", encoding="utf-8")

        hidden_file = tmpdir / ".hidden.py"
        hidden_file.write_text("y = 2", encoding="utf-8")

        stats = warmup_index(tmpdir)

        # Should only index visible file
        assert stats["indexed"] == 1
        assert stats["errors"] == 0


def test_warmup_index_deterministic():
    """Test that warmup_index produces deterministic output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test files
        for i in range(3):
            test_file = tmpdir / f"test{i}.py"
            test_file.write_text(f"x{i} = {i}", encoding="utf-8")

        # Run warmup twice
        stats1 = warmup_index(tmpdir)
        stats2 = warmup_index(tmpdir)

        # Should produce identical results
        assert stats1["indexed"] == stats2["indexed"]
        assert stats1["errors"] == stats2["errors"]

        # Index file should be deterministic
        index_file = tmpdir / ".ace" / "index.json"
        content1 = index_file.read_text(encoding="utf-8")

        # Run again
        warmup_index(tmpdir)
        content2 = index_file.read_text(encoding="utf-8")

        # Content should be identical
        assert content1 == content2
