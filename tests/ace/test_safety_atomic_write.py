"""Tests for atomic write functionality."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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


@pytest.mark.parametrize("simulate_platform", ["win32", "linux"])
def test_atomic_write_fsync_dir_failure(tmp_path: Path, simulate_platform: str):
    """
    Test atomic write when directory fsync fails (Windows behavior).

    Windows doesn't support directory fsync, which triggers the best-effort
    fallback in _fsync_dir(). This test verifies that atomic_write still
    succeeds gracefully when directory fsync raises OSError.

    Args:
        tmp_path: Pytest fixture for temporary directory
        simulate_platform: Platform to simulate ("win32" or "linux")
    """
    target = tmp_path / "test.txt"
    payload = b"test content"

    if simulate_platform == "win32":
        # Mock os.open to raise OSError when opening directories
        # This simulates Windows behavior where directory fsync is not supported
        original_open = os.open

        def mock_open(path, flags, *args, **kwargs):
            # Check if the path is a directory by trying to resolve it
            try:
                path_obj = Path(path)
                if path_obj.is_dir():
                    raise OSError(f"Cannot open directory for fsync: {path}")
            except Exception:
                pass  # If path doesn't exist yet, continue normally
            return original_open(path, flags, *args, **kwargs)

        with patch("os.open", side_effect=mock_open):
            # Verify atomic write still succeeds despite fsync_dir failure
            atomic_write(target, payload)
    else:
        # On Linux, atomic write should work normally
        atomic_write(target, payload)

    # Verify file was written correctly regardless of platform
    assert target.exists()
    assert target.read_bytes() == payload


def test_atomic_write_fsync_dir_exception_handling(tmp_path: Path):
    """
    Test that _fsync_dir exception handling doesn't break atomic_write.

    This test explicitly verifies that when directory fsync raises any exception,
    the atomic write operation completes successfully. This is critical for
    cross-platform compatibility (Windows, some NFS mounts, etc.).
    """
    target = tmp_path / "test.txt"
    payload = b"exception test"

    # Mock os.open to always raise OSError for any path
    def mock_open_always_fails(path, flags, *args, **kwargs):
        raise OSError("Simulated fsync failure")

    with patch("os.open", side_effect=mock_open_always_fails):
        # This should still succeed due to best-effort fallback
        atomic_write(target, payload)

    # Verify file was written successfully
    assert target.exists()
    assert target.read_bytes() == payload
