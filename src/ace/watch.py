"""Watch mode - Lightweight file change detection and auto-analysis.

Simple polling-based watch (no heavy dependencies). Detects file changes and
runs incremental analysis automatically.
"""

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FileSnapshot:
    """Snapshot of a file's state."""

    path: Path
    mtime: float
    size: int
    hash: str

    @staticmethod
    def create(path: Path) -> "FileSnapshot":
        """Create snapshot of current file state."""
        stat = path.stat()
        # For small files, compute hash for accurate change detection
        if stat.st_size < 1_000_000:  # 1MB
            with open(path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        else:
            # For large files, use mtime + size
            content_hash = f"{stat.st_mtime}:{stat.st_size}"

        return FileSnapshot(
            path=path,
            mtime=stat.st_mtime,
            size=stat.st_size,
            hash=content_hash,
        )


@dataclass
class ChangeSet:
    """Set of file changes detected."""

    added: list[Path]
    modified: list[Path]
    deleted: list[Path]
    timestamp: float

    def is_empty(self) -> bool:
        """Check if changeset is empty."""
        return not (self.added or self.modified or self.deleted)

    def all_changed(self) -> list[Path]:
        """Get all changed files (added + modified)."""
        return self.added + self.modified

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = []
        if self.added:
            lines.append(f"  Added: {len(self.added)} file(s)")
        if self.modified:
            lines.append(f"  Modified: {len(self.modified)} file(s)")
        if self.deleted:
            lines.append(f"  Deleted: {len(self.deleted)} file(s)")
        return "\n".join(lines) if lines else "  No changes"


class FileWatcher:
    """
    Lightweight file watcher using polling.

    No external dependencies - uses simple stat-based polling with optional
    content hashing for small files.
    """

    def __init__(
        self,
        target: Path,
        poll_interval: float = 1.0,
        ignore_patterns: list[str] | None = None,
    ):
        """
        Initialize file watcher.

        Args:
            target: Directory or file to watch
            poll_interval: Polling interval in seconds (default: 1.0)
            ignore_patterns: Glob patterns to ignore (default: [".ace/**", "**/__pycache__/**"])
        """
        self.target = target.resolve()
        self.poll_interval = poll_interval
        self.ignore_patterns = ignore_patterns or [
            ".ace/**",
            "**/__pycache__/**",
            "**/.git/**",
            "**/.venv/**",
            "**/venv/**",
            "**/*.pyc",
            "**/.pytest_cache/**",
            "**/.mypy_cache/**",
            "**/.ruff_cache/**",
        ]
        self.snapshots: dict[Path, FileSnapshot] = {}
        self.last_scan_time = 0.0

    def should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        from fnmatch import fnmatch

        path_str = str(path)
        for pattern in self.ignore_patterns:
            if fnmatch(path_str, pattern) or fnmatch(path.name, pattern):
                return True
        return False

    def scan_files(self) -> list[Path]:
        """Scan target directory for files."""
        if self.target.is_file():
            return [self.target] if not self.should_ignore(self.target) else []

        files = []
        try:
            for path in self.target.rglob("*"):
                if path.is_file() and not self.should_ignore(path):
                    files.append(path)
        except Exception:
            # Ignore permission errors, etc.
            pass

        return sorted(files)

    def detect_changes(self) -> ChangeSet:
        """
        Detect file changes since last scan.

        Returns:
            ChangeSet with added, modified, and deleted files
        """
        current_time = time.time()
        current_files = self.scan_files()

        # Build new snapshots
        new_snapshots: dict[Path, FileSnapshot] = {}
        for path in current_files:
            try:
                new_snapshots[path] = FileSnapshot.create(path)
            except Exception:
                # File disappeared or permission error
                pass

        # Detect changes
        added = []
        modified = []
        deleted = []

        # Check for added and modified
        for path, new_snap in new_snapshots.items():
            if path not in self.snapshots:
                added.append(path)
            else:
                old_snap = self.snapshots[path]
                # Compare hash for accurate change detection
                if new_snap.hash != old_snap.hash:
                    modified.append(path)

        # Check for deleted
        for path in self.snapshots:
            if path not in new_snapshots:
                deleted.append(path)

        # Update snapshots
        self.snapshots = new_snapshots
        self.last_scan_time = current_time

        return ChangeSet(
            added=sorted(added),
            modified=sorted(modified),
            deleted=sorted(deleted),
            timestamp=current_time,
        )

    def initial_scan(self) -> None:
        """Perform initial scan to establish baseline."""
        self.detect_changes()

    def wait_for_changes(self, timeout: float | None = None) -> ChangeSet:
        """
        Wait for file changes (blocking).

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            ChangeSet when changes detected, or empty ChangeSet on timeout
        """
        start_time = time.time()

        while True:
            changes = self.detect_changes()

            if not changes.is_empty():
                return changes

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return ChangeSet([], [], [], time.time())

            # Sleep before next poll
            time.sleep(self.poll_interval)


def watch_loop(
    target: Path,
    poll_interval: float = 1.0,
    ignore_patterns: list[str] | None = None,
    callback: Any = None,
    max_iterations: int | None = None,
) -> None:
    """
    Run watch loop continuously.

    Args:
        target: Directory or file to watch
        poll_interval: Polling interval in seconds
        ignore_patterns: Patterns to ignore
        callback: Function to call on changes: callback(changeset) -> bool (continue?)
        max_iterations: Maximum iterations (for testing, None = infinite)
    """
    watcher = FileWatcher(target, poll_interval, ignore_patterns)

    # Initial scan
    print(f"👀 Watching {target} (poll interval: {poll_interval}s)")
    print("Press Ctrl+C to stop\n")
    watcher.initial_scan()

    iterations = 0
    try:
        while max_iterations is None or iterations < max_iterations:
            # Wait for changes
            changes = watcher.wait_for_changes(timeout=None)

            if not changes.is_empty():
                print(f"\n📝 Changes detected at {time.strftime('%H:%M:%S')}:")
                print(changes.summary())
                print()

                # Call callback if provided
                if callback:
                    should_continue = callback(changes)
                    if not should_continue:
                        break

            iterations += 1

    except KeyboardInterrupt:
        print("\n\n👋 Watch stopped")


def debounce_changes(
    watcher: FileWatcher,
    debounce_time: float = 0.5,
) -> ChangeSet:
    """
    Detect changes with debouncing.

    Waits for debounce_time after last change before returning.

    Args:
        watcher: FileWatcher instance
        debounce_time: Debounce time in seconds

    Returns:
        Debounced ChangeSet
    """
    accumulated_changes = ChangeSet([], [], [], time.time())
    last_change_time = 0.0

    while True:
        changes = watcher.detect_changes()

        if not changes.is_empty():
            # Accumulate changes
            accumulated_changes.added.extend(changes.added)
            accumulated_changes.modified.extend(changes.modified)
            accumulated_changes.deleted.extend(changes.deleted)
            last_change_time = time.time()

        # If we've seen changes and enough time has passed, return
        if last_change_time > 0:
            elapsed = time.time() - last_change_time
            if elapsed >= debounce_time:
                # Deduplicate
                accumulated_changes.added = sorted(set(accumulated_changes.added))
                accumulated_changes.modified = sorted(set(accumulated_changes.modified))
                accumulated_changes.deleted = sorted(set(accumulated_changes.deleted))
                return accumulated_changes

        time.sleep(watcher.poll_interval)


def format_change_summary(
    changes: ChangeSet,
    findings_before: int,
    findings_after: int,
) -> str:
    """
    Format change summary for display.

    Args:
        changes: ChangeSet
        findings_before: Number of findings before analysis
        findings_after: Number of findings after analysis

    Returns:
        Formatted summary string
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"📊 Analysis Summary ({time.strftime('%H:%M:%S')})")
    lines.append("=" * 60)
    lines.append("")

    # Changes
    lines.append("Files changed:")
    lines.append(changes.summary())
    lines.append("")

    # Findings delta
    delta = findings_after - findings_before
    if delta > 0:
        lines.append(f"⚠️  Findings: {findings_before} → {findings_after} (+{delta})")
    elif delta < 0:
        lines.append(f"✅ Findings: {findings_before} → {findings_after} ({delta})")
    else:
        lines.append(f"◯  Findings: {findings_after} (no change)")

    lines.append("=" * 60)
    return "\n".join(lines)
