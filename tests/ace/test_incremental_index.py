"""Tests for incremental scanning and content index."""

import tempfile
from pathlib import Path

from ace.index import ContentIndex, compute_file_hash, is_indexable


def test_content_index_add_file():
    """Test adding file to content index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 + 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        entry = index.add_file(test_file)

        assert entry.path == str(test_file)
        assert entry.size == test_file.stat().st_size
        assert len(entry.sha256) == 64  # SHA256 hex digest


def test_content_index_has_changed_new_file():
    """Test has_changed returns True for new files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 + 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        # File not in index yet
        assert index.has_changed(test_file) is True


def test_content_index_has_changed_unchanged_file():
    """Test has_changed returns False for unchanged files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 + 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        # Add file to index
        index.add_file(test_file)

        # File should not be marked as changed
        assert index.has_changed(test_file) is False


def test_content_index_has_changed_modified_file():
    """Test has_changed returns True for modified files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 + 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        # Add file to index
        index.add_file(test_file)

        # Modify file
        test_file.write_text("x = 1 + 3")

        # File should be marked as changed
        assert index.has_changed(test_file) is True


def test_content_index_save_and_load():
    """Test saving and loading index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 + 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        # Add file and save
        index.add_file(test_file)
        index.save()

        # Load into new index
        index2 = ContentIndex(index_path)
        index2.load()

        # Should have same entry
        assert str(test_file) in index2.entries
        assert index2.entries[str(test_file)].size == test_file.stat().st_size


def test_content_index_get_changed_files():
    """Test filtering changed files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "test1.py"
        file2 = Path(tmpdir) / "test2.py"
        file1.write_text("x = 1")
        file2.write_text("y = 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        # Add only file1 to index
        index.add_file(file1)

        # Get changed files (file2 should be new)
        changed = index.get_changed_files([file1, file2])

        # Only file2 should be in changed list
        assert file2 in changed
        assert file1 not in changed


def test_content_index_rebuild():
    """Test rebuilding index from scratch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "test1.py"
        file2 = Path(tmpdir) / "test2.py"
        file1.write_text("x = 1")
        file2.write_text("y = 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        # Rebuild with both files
        index.rebuild([file1, file2])

        # Both files should be in index
        assert str(file1) in index.entries
        assert str(file2) in index.entries


def test_content_index_remove_file():
    """Test removing file from index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        # Add and remove file
        index.add_file(test_file)
        assert str(test_file) in index.entries

        index.remove_file(test_file)
        assert str(test_file) not in index.entries


def test_content_index_get_stats():
    """Test getting index statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "test1.py"
        file2 = Path(tmpdir) / "test2.py"
        file1.write_text("x = 1")
        file2.write_text("y = 2")

        index_path = Path(tmpdir) / "index.json"
        index = ContentIndex(index_path)

        index.add_file(file1)
        index.add_file(file2)

        stats = index.get_stats()

        assert stats["total_files"] == 2
        assert stats["total_size"] > 0


def test_compute_file_hash():
    """Test computing file hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("hello world")

        hash_val = compute_file_hash(test_file)

        # Should be valid hex string
        assert len(hash_val) == 64
        assert all(c in "0123456789abcdef" for c in hash_val)


def test_is_indexable_python_file():
    """Test that Python files are indexable."""
    assert is_indexable(Path("test.py")) is True


def test_is_indexable_hidden_file():
    """Test that hidden files are not indexable."""
    assert is_indexable(Path(".hidden")) is False


def test_is_indexable_binary_file():
    """Test that binary files are not indexable."""
    assert is_indexable(Path("test.pyc")) is False
    assert is_indexable(Path("test.jpg")) is False
