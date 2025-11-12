"""Tests for watch mode."""

import tempfile
import time
from pathlib import Path

import pytest

from ace.watch import (
    ChangeSet,
    FileSnapshot,
    FileWatcher,
    debounce_changes,
    format_change_summary,
)


class TestFileSnapshot:
    """Tests for FileSnapshot."""

    def test_create_snapshot(self):
        """Test creating file snapshot."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('hello')")
            f.flush()
            path = Path(f.name)

        try:
            snapshot = FileSnapshot.create(path)
            assert snapshot.path == path
            assert snapshot.size > 0
            assert len(snapshot.hash) > 0
        finally:
            path.unlink()

    def test_snapshot_detects_changes(self):
        """Test that snapshot detects content changes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('hello')")
            f.flush()
            path = Path(f.name)

        try:
            snapshot1 = FileSnapshot.create(path)

            # Modify file
            time.sleep(0.01)  # Ensure mtime changes
            path.write_text("print('world')")

            snapshot2 = FileSnapshot.create(path)

            assert snapshot1.hash != snapshot2.hash
        finally:
            path.unlink()


class TestChangeSet:
    """Tests for ChangeSet."""

    def test_empty_changeset(self):
        """Test empty changeset."""
        changes = ChangeSet([], [], [], time.time())
        assert changes.is_empty()

    def test_non_empty_changeset(self):
        """Test non-empty changeset."""
        changes = ChangeSet([Path("a.py")], [], [], time.time())
        assert not changes.is_empty()

    def test_all_changed(self):
        """Test all_changed includes added and modified."""
        changes = ChangeSet(
            [Path("a.py")], [Path("b.py")], [Path("c.py")], time.time()
        )
        all_changed = changes.all_changed()
        assert len(all_changed) == 2
        assert Path("a.py") in all_changed
        assert Path("b.py") in all_changed

    def test_summary(self):
        """Test summary generation."""
        changes = ChangeSet([Path("a.py")], [Path("b.py")], [], time.time())
        summary = changes.summary()
        assert "Added: 1" in summary
        assert "Modified: 1" in summary


class TestFileWatcher:
    """Tests for FileWatcher."""

    def test_init(self):
        """Test watcher initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = FileWatcher(Path(tmpdir))
            assert watcher.target.exists()
            assert len(watcher.snapshots) == 0

    def test_should_ignore(self):
        """Test ignore patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = FileWatcher(Path(tmpdir))

            assert watcher.should_ignore(Path(".ace/cache.db"))
            assert watcher.should_ignore(Path("__pycache__/test.pyc"))
            assert not watcher.should_ignore(Path("test.py"))

    def test_scan_files(self):
        """Test file scanning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "test.py").write_text("print('test')")
            (tmpdir_path / "README.md").write_text("# Test")

            watcher = FileWatcher(tmpdir_path)
            files = watcher.scan_files()

            assert len(files) >= 2
            assert any(f.name == "test.py" for f in files)

    def test_detect_added_files(self):
        """Test detection of added files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            watcher = FileWatcher(tmpdir_path)
            watcher.initial_scan()

            # Add new file
            (tmpdir_path / "new.py").write_text("print('new')")

            changes = watcher.detect_changes()

            assert len(changes.added) == 1
            assert changes.added[0].name == "new.py"

    def test_detect_modified_files(self):
        """Test detection of modified files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create initial file
            test_file = tmpdir_path / "test.py"
            test_file.write_text("print('v1')")

            watcher = FileWatcher(tmpdir_path)
            watcher.initial_scan()

            # Modify file
            time.sleep(0.01)
            test_file.write_text("print('v2')")

            changes = watcher.detect_changes()

            assert len(changes.modified) == 1
            assert changes.modified[0].name == "test.py"

    def test_detect_deleted_files(self):
        """Test detection of deleted files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create file
            test_file = tmpdir_path / "test.py"
            test_file.write_text("print('test')")

            watcher = FileWatcher(tmpdir_path)
            watcher.initial_scan()

            # Delete file
            test_file.unlink()

            changes = watcher.detect_changes()

            assert len(changes.deleted) == 1
            assert changes.deleted[0].name == "test.py"


class TestFormatChangeSummary:
    """Tests for change summary formatting."""

    def test_format_summary(self):
        """Test formatting change summary."""
        changes = ChangeSet([Path("a.py")], [], [], time.time())
        summary = format_change_summary(changes, 10, 15)

        assert "Analysis Summary" in summary
        assert "Added: 1" in summary
        assert "+5" in summary  # Delta
