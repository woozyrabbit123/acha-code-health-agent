"""
Content index for incremental scanning and cache warmup.

Tracks file metadata (size, mtime, sha256) to enable efficient incremental
analysis by skipping unchanged files.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ace.safety import atomic_write


@dataclass
class FileEntry:
    """Metadata for a single file in the index."""
    path: str
    size: int
    mtime: float  # Modification time (seconds since epoch)
    sha256: str  # Hex digest (no prefix)
    clean_runs_count: int = 0  # Number of consecutive clean runs (no changes)


class ContentIndex:
    """
    Content index for tracking file changes.

    Format: JSON file with deterministic serialization
    Location: .ace/index.json
    """

    def __init__(self, index_path: Path = Path(".ace/index.json")):
        self.index_path = index_path
        self.entries: dict[str, FileEntry] = {}

    def load(self) -> None:
        """Load index from disk if it exists."""
        if not self.index_path.exists():
            self.entries = {}
            return

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.entries = {}
            for path_str, entry_dict in data.items():
                self.entries[path_str] = FileEntry(
                    path=entry_dict["path"],
                    size=entry_dict["size"],
                    mtime=entry_dict["mtime"],
                    sha256=entry_dict["sha256"],
                    clean_runs_count=entry_dict.get("clean_runs_count", 0)
                )
        except (json.JSONDecodeError, KeyError, OSError):
            # If index is corrupted, start fresh
            self.entries = {}

    def save(self) -> None:
        """Save index to disk with deterministic serialization and atomic write."""
        # Convert to dict for JSON serialization
        data = {}
        for path_str, entry in sorted(self.entries.items()):
            data[path_str] = {
                "path": entry.path,
                "size": entry.size,
                "mtime": entry.mtime,
                "sha256": entry.sha256,
                "clean_runs_count": entry.clean_runs_count
            }

        # Write with deterministic formatting and atomic write for durability
        content = json.dumps(data, indent=2, sort_keys=True).encode('utf-8')
        content += b"\n"  # Trailing newline
        atomic_write(self.index_path, content)

    def add_file(self, file_path: Path, preserve_clean_runs: bool = False) -> FileEntry:
        """
        Add or update file entry in index.

        Computes file hash and stores metadata.

        Args:
            file_path: Path to file to index
            preserve_clean_runs: If True and file exists, preserve clean_runs_count

        Returns:
            FileEntry for the file

        Raises:
            OSError: If file cannot be read
        """
        # Read file and compute hash
        content = file_path.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()

        # Get file stats
        stat = file_path.stat()

        # Get existing clean_runs_count if preserving
        clean_runs = 0
        if preserve_clean_runs:
            path_str = str(file_path)
            if path_str in self.entries:
                clean_runs = self.entries[path_str].clean_runs_count

        # Create entry
        entry = FileEntry(
            path=str(file_path),
            size=stat.st_size,
            mtime=stat.st_mtime,
            sha256=sha256,
            clean_runs_count=clean_runs
        )

        # Store in index
        self.entries[str(file_path)] = entry

        return entry

    def has_changed(self, file_path: Path) -> bool:
        """
        Check if file has changed since last index.

        Uses fast mtime check first, then validates with hash if needed.

        Args:
            file_path: Path to file to check

        Returns:
            True if file is new or has changed, False if unchanged
        """
        path_str = str(file_path)

        # File not in index -> changed (new)
        if path_str not in self.entries:
            return True

        entry = self.entries[path_str]

        # File doesn't exist anymore -> changed (deleted)
        if not file_path.exists():
            return True

        # Fast check: size or mtime changed
        stat = file_path.stat()
        if stat.st_size != entry.size or stat.st_mtime != entry.mtime:
            return True

        # Slow check: verify hash (mtime can be unreliable)
        # Only do this if mtime/size match but we want to be sure
        try:
            content = file_path.read_bytes()
            current_sha256 = hashlib.sha256(content).hexdigest()
            return current_sha256 != entry.sha256
        except OSError:
            # Can't read file -> assume changed
            return True

    def get_changed_files(self, files: list[Path]) -> list[Path]:
        """
        Filter file list to only those that have changed.

        Args:
            files: List of file paths to check

        Returns:
            List of files that are new or have changed since last index
        """
        changed = []
        for file_path in files:
            if self.has_changed(file_path):
                changed.append(file_path)
        return changed

    def rebuild(self, files: list[Path]) -> None:
        """
        Rebuild index from scratch for given files.

        Args:
            files: List of file paths to index
        """
        self.entries = {}
        for file_path in files:
            try:
                self.add_file(file_path)
            except OSError:
                # Skip files that can't be read
                continue

    def remove_file(self, file_path: Path) -> None:
        """
        Remove file from index.

        Args:
            file_path: Path to file to remove
        """
        path_str = str(file_path)
        if path_str in self.entries:
            del self.entries[path_str]

    def get_stats(self) -> dict[str, int]:
        """
        Get index statistics.

        Returns:
            Dictionary with index stats (total_files, total_size)
        """
        total_files = len(self.entries)
        total_size = sum(entry.size for entry in self.entries.values())

        return {
            "total_files": total_files,
            "total_size": total_size
        }

    def increment_clean_runs(self, file_path: Path) -> None:
        """
        Increment clean runs count for a file.

        Args:
            file_path: Path to file
        """
        path_str = str(file_path)
        if path_str in self.entries:
            self.entries[path_str].clean_runs_count += 1

    def reset_clean_runs(self, file_path: Path) -> None:
        """
        Reset clean runs count for a file (e.g., when file changes).

        Args:
            file_path: Path to file
        """
        path_str = str(file_path)
        if path_str in self.entries:
            self.entries[path_str].clean_runs_count = 0

    def should_skip_deep_scan(self, file_path: Path, threshold: int = 3) -> bool:
        """
        Check if file should skip deep scan based on clean-skip heuristic.

        Files with >= threshold consecutive clean runs can skip deep scans
        and only run quick detects.

        Args:
            file_path: Path to file
            threshold: Minimum clean runs to skip deep scan (default: 3)

        Returns:
            True if file should skip deep scan
        """
        path_str = str(file_path)
        if path_str not in self.entries:
            return False

        entry = self.entries[path_str]

        # Skip deep scan if file has been clean for threshold or more runs
        return entry.clean_runs_count >= threshold


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of file content.

    Args:
        file_path: Path to file

    Returns:
        Hex digest (no prefix)

    Raises:
        OSError: If file cannot be read

    Examples:
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        ...     _ = f.write("hello world")
        ...     temp_path = f.name
        >>> hash_val = compute_file_hash(Path(temp_path))
        >>> hash_val == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        True
        >>> import os
        >>> os.unlink(temp_path)
    """
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def is_indexable(file_path: Path) -> bool:
    """
    Check if file should be included in index.

    Excludes binary files, hidden files (starting with .), and large files.

    Args:
        file_path: Path to check

    Returns:
        True if file should be indexed

    Examples:
        >>> is_indexable(Path("test.py"))
        True
        >>> is_indexable(Path(".hidden"))
        False
        >>> is_indexable(Path("test.pyc"))
        False
    """
    # Exclude hidden files
    if file_path.name.startswith("."):
        return False

    # Exclude common binary extensions
    binary_exts = {
        ".pyc", ".pyo", ".so", ".dylib", ".dll",
        ".exe", ".bin", ".jpg", ".jpeg", ".png", ".gif",
        ".pdf", ".zip", ".tar", ".gz", ".bz2"
    }
    if file_path.suffix.lower() in binary_exts:
        return False

    # Exclude very large files (>10MB) - only check if file exists
    if file_path.exists():
        try:
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return False
        except OSError:
            return False

    return True


def warmup_index(target: Path) -> dict[str, int]:
    """
    Build or rebuild content index for a target path.

    This is a deterministic operation that scans all indexable files
    in the target and updates the content index with their metadata.

    Args:
        target: Target directory or file to index

    Returns:
        Dictionary with stats: {"indexed": count, "skipped": count, "errors": count}
    """
    # Determine index path based on target
    if target.is_file():
        # For single file, use .ace in parent directory
        index_path = target.parent / ".ace" / "index.json"
    else:
        # For directory, use .ace inside the directory
        index_path = target / ".ace" / "index.json"

    index = ContentIndex(index_path=index_path)

    # Load existing index (if any)
    index.load()

    # Collect files to index
    if target.is_file():
        files = [target] if is_indexable(target) else []
    else:
        files = sorted(target.rglob("*"))
        # Filter for indexable files, excluding .ace directory
        files = [
            f for f in files
            if f.is_file() and is_indexable(f) and ".ace" not in f.parts
        ]

    stats = {"indexed": 0, "skipped": 0, "errors": 0}

    # Index each file
    for file_path in files:
        try:
            index.add_file(file_path)
            stats["indexed"] += 1
        except OSError:
            # Skip files that can't be read
            stats["errors"] += 1
        except Exception:
            stats["errors"] += 1

    # Save index
    index.save()

    return stats
