"""Tests for atomic write functionality."""
import tempfile
from pathlib import Path

from ace.safety import atomic_write


def test_atomic_write_basic(tmp_path: Path):
    """Test basic atomic write functionality."""
    target = tmp_path / "test.txt"
    payload = b"hello world"

    atomic_write(target, payload)

    assert target.exists()
    assert target.read_bytes() == payload


def test_atomic_write_large_file(tmp_path: Path):
    """Test atomic write with large payload (2MB)."""
    target = tmp_path / "big.txt"
    payload = b"A" * (2 * 1024 * 1024)  # 2 MB

    atomic_write(target, payload)

    assert target.exists()
    assert target.read_bytes() == payload


def test_atomic_write_creates_parent_dirs(tmp_path: Path):
    """Test that atomic write creates parent directories."""
    target = tmp_path / "subdir" / "nested" / "test.txt"
    payload = b"test data"

    atomic_write(target, payload)

    assert target.exists()
    assert target.read_bytes() == payload


def test_atomic_write_overwrites_existing(tmp_path: Path):
    """Test that atomic write overwrites existing files."""
    target = tmp_path / "test.txt"
    target.write_bytes(b"old content")

    new_payload = b"new content"
    atomic_write(target, new_payload)

    assert target.read_bytes() == new_payload
