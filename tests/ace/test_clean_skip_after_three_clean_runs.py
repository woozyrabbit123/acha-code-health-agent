"""Test clean-skip heuristic after three clean runs."""

import tempfile
from pathlib import Path

import pytest

from ace.index import ContentIndex


def test_clean_skip_after_three_clean_runs():
    """Test that files skip deep scan after 3 consecutive clean runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        index_path = tmpdir / ".ace" / "index.json"
        test_file = tmpdir / "test.py"

        # Create test file
        test_file.write_text("print('hello')\n")

        # Create index
        index = ContentIndex(index_path=index_path)

        # Add file (clean_runs_count = 0)
        index.add_file(test_file)
        assert not index.should_skip_deep_scan(test_file, threshold=3)

        # Simulate 3 clean runs
        for i in range(3):
            index.increment_clean_runs(test_file)
            index.save()

            # Check skip status
            if i < 2:
                # Not yet at threshold
                assert not index.should_skip_deep_scan(test_file, threshold=3)
            else:
                # At threshold, should skip
                assert index.should_skip_deep_scan(test_file, threshold=3)

        # Verify clean_runs_count
        entry = index.entries[str(test_file)]
        assert entry.clean_runs_count == 3

        # Load from disk and verify persistence
        index2 = ContentIndex(index_path=index_path)
        index2.load()
        assert index2.should_skip_deep_scan(test_file, threshold=3)

        # Verify entry was loaded correctly
        entry2 = index2.entries[str(test_file)]
        assert entry2.clean_runs_count == 3


def test_clean_skip_resets_on_change():
    """Test that clean_runs_count resets when file changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        index_path = tmpdir / ".ace" / "index.json"
        test_file = tmpdir / "test.py"

        # Create test file
        test_file.write_text("print('hello')\n")

        # Create index
        index = ContentIndex(index_path=index_path)

        # Add file and increment to threshold
        index.add_file(test_file)
        for _ in range(3):
            index.increment_clean_runs(test_file)

        assert index.should_skip_deep_scan(test_file, threshold=3)

        # Reset clean runs (simulates file change detected)
        index.reset_clean_runs(test_file)
        assert not index.should_skip_deep_scan(test_file, threshold=3)

        # Verify count is 0
        entry = index.entries[str(test_file)]
        assert entry.clean_runs_count == 0


def test_clean_skip_with_different_thresholds():
    """Test clean-skip with different threshold values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        index_path = tmpdir / ".ace" / "index.json"
        test_file = tmpdir / "test.py"

        # Create test file
        test_file.write_text("print('hello')\n")

        # Create index
        index = ContentIndex(index_path=index_path)
        index.add_file(test_file)

        # Increment twice
        index.increment_clean_runs(test_file)
        index.increment_clean_runs(test_file)

        # clean_runs_count = 2

        # Should not skip with threshold=3
        assert not index.should_skip_deep_scan(test_file, threshold=3)

        # Should skip with threshold=2
        assert index.should_skip_deep_scan(test_file, threshold=2)

        # Should skip with threshold=1
        assert index.should_skip_deep_scan(test_file, threshold=1)


def test_clean_skip_file_not_in_index():
    """Test that files not in index don't skip deep scan."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        index_path = tmpdir / ".ace" / "index.json"
        test_file = tmpdir / "test.py"

        # Create test file but don't add to index
        test_file.write_text("print('hello')\n")

        # Create index
        index = ContentIndex(index_path=index_path)

        # File not in index should not skip
        assert not index.should_skip_deep_scan(test_file, threshold=3)


def test_clean_skip_preserves_count_on_update():
    """Test that clean_runs_count is preserved when using preserve_clean_runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        index_path = tmpdir / ".ace" / "index.json"
        test_file = tmpdir / "test.py"

        # Create test file
        test_file.write_text("print('hello')\n")

        # Create index
        index = ContentIndex(index_path=index_path)

        # Add file and increment
        index.add_file(test_file)
        index.increment_clean_runs(test_file)
        index.increment_clean_runs(test_file)

        entry = index.entries[str(test_file)]
        assert entry.clean_runs_count == 2

        # Update file with preserve_clean_runs=True
        index.add_file(test_file, preserve_clean_runs=True)

        # Count should be preserved
        entry = index.entries[str(test_file)]
        assert entry.clean_runs_count == 2

        # Update file with preserve_clean_runs=False (default)
        index.add_file(test_file, preserve_clean_runs=False)

        # Count should be reset to 0
        entry = index.entries[str(test_file)]
        assert entry.clean_runs_count == 0


def test_clean_skip_multiple_files():
    """Test clean-skip with multiple files at different clean run counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        index_path = tmpdir / ".ace" / "index.json"

        # Create multiple test files
        file1 = tmpdir / "file1.py"
        file2 = tmpdir / "file2.py"
        file3 = tmpdir / "file3.py"

        file1.write_text("print('1')\n")
        file2.write_text("print('2')\n")
        file3.write_text("print('3')\n")

        # Create index
        index = ContentIndex(index_path=index_path)

        # Add files
        index.add_file(file1)
        index.add_file(file2)
        index.add_file(file3)

        # file1: 1 clean run
        index.increment_clean_runs(file1)

        # file2: 3 clean runs
        for _ in range(3):
            index.increment_clean_runs(file2)

        # file3: 5 clean runs
        for _ in range(5):
            index.increment_clean_runs(file3)

        # Check skip status
        assert not index.should_skip_deep_scan(file1, threshold=3)
        assert index.should_skip_deep_scan(file2, threshold=3)
        assert index.should_skip_deep_scan(file3, threshold=3)

        # Save and reload
        index.save()
        index2 = ContentIndex(index_path=index_path)
        index2.load()

        # Verify persistence
        assert not index2.should_skip_deep_scan(file1, threshold=3)
        assert index2.should_skip_deep_scan(file2, threshold=3)
        assert index2.should_skip_deep_scan(file3, threshold=3)
