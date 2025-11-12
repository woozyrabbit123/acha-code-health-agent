"""
Journal system for safe, reversible edits without git.

Provides append-only JSONL logging of file modifications with fsync guarantees,
enabling exact restoration of file states.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class JournalIntent:
    """Intent to modify a file before applying changes."""
    timestamp: str
    file: str
    before_sha: str
    before_size: int
    rule_ids: list[str]
    plan_id: str
    pre_image: str  # Full original content for restore


@dataclass
class JournalSuccess:
    """Successful modification of a file."""
    timestamp: str
    file: str
    after_sha: str
    after_size: int
    receipt_id: str


@dataclass
class JournalRevert:
    """Revert operation record."""
    timestamp: str
    file: str
    from_sha: str
    to_sha: str
    reason: str


class Journal:
    """
    Append-only journal for tracking file modifications.

    Format: JSONL (one JSON object per line)
    Location: .ace/journals/<run_id>.jsonl
    Guarantees: fsync after each write for crash safety

    Each entry has a 'type' field: 'intent', 'success', or 'revert'
    """

    def __init__(self, run_id: str, journal_dir: Path = Path(".ace/journals")):
        self.run_id = run_id
        self.journal_dir = journal_dir
        self.journal_path = journal_dir / f"{run_id}.jsonl"
        self._handle = None

        # Ensure journal directory exists
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    def _append(self, entry: dict[str, Any]) -> None:
        """Append entry to journal with fsync guarantee."""
        if self._handle is None:
            self._handle = open(self.journal_path, "a", encoding="utf-8")

        line = json.dumps(entry, separators=(',', ':'), sort_keys=True)
        self._handle.write(line + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def log_intent(
        self,
        file: str,
        before_sha: str,
        before_size: int,
        rule_ids: list[str],
        plan_id: str,
        pre_image: bytes
    ) -> None:
        """
        Log intent to modify a file.

        Args:
            file: Path to file being modified
            before_sha: SHA256 hash of file before modification
            before_size: Size in bytes before modification
            rule_ids: Rule IDs triggering this modification
            plan_id: Plan identifier
            pre_image: Full original content for restore (no truncation)
        """
        entry = {
            "type": "intent",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": file,
            "before_sha": before_sha,
            "before_size": before_size,
            "rule_ids": sorted(rule_ids),
            "plan_id": plan_id,
            "pre_image": pre_image.decode("utf-8", errors="surrogateescape")  # Full content
        }
        self._append(entry)

    def log_success(
        self,
        file: str,
        after_sha: str,
        after_size: int,
        receipt_id: str
    ) -> None:
        """
        Log successful modification of a file.

        Args:
            file: Path to file that was modified
            after_sha: SHA256 hash of file after modification
            after_size: Size in bytes after modification
            receipt_id: Receipt identifier for this operation
        """
        entry = {
            "type": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": file,
            "after_sha": after_sha,
            "after_size": after_size,
            "receipt_id": receipt_id
        }
        self._append(entry)

    def log_revert(
        self,
        file: str,
        from_sha: str,
        to_sha: str,
        reason: str
    ) -> None:
        """
        Log revert operation.

        Args:
            file: Path to file being reverted
            from_sha: SHA256 hash before revert
            to_sha: SHA256 hash after revert (should match original before_sha)
            reason: Reason for revert (e.g., "parse-fail", "manual")
        """
        entry = {
            "type": "revert",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": file,
            "from_sha": from_sha,
            "to_sha": to_sha,
            "reason": reason
        }
        self._append(entry)

    def close(self) -> None:
        """Close journal file handle."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


@dataclass
class JournalEntry:
    """Parsed journal entry with file modification details."""
    type: str  # 'intent', 'success', or 'revert'
    timestamp: str
    file: str
    data: dict[str, Any]  # Type-specific fields


def read_journal(journal_path: Path) -> list[JournalEntry]:
    """
    Read and parse journal file.

    Args:
        journal_path: Path to journal file (.jsonl)

    Returns:
        List of parsed journal entries in order
    """
    if not journal_path.exists():
        return []

    entries = []
    with open(journal_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            entry_dict = json.loads(line)
            entry = JournalEntry(
                type=entry_dict["type"],
                timestamp=entry_dict["timestamp"],
                file=entry_dict["file"],
                data=entry_dict
            )
            entries.append(entry)

    return entries


@dataclass
class RevertContext:
    """Context for reverting a file modification."""
    file: str
    expected_current_sha: str  # SHA we expect file to have now
    restore_content: bytes  # Content to restore
    original_sha: str  # SHA to verify after restore
    plan_id: str
    rule_ids: list[str]


def build_revert_plan(journal_path: Path) -> list[RevertContext]:
    """
    Build revert plan from journal (reverse order).

    Matches intent/success pairs and creates revert contexts.
    Only includes successful modifications (both intent and success present).
    Returns in reverse order (most recent first).

    Args:
        journal_path: Path to journal file

    Returns:
        List of RevertContext objects in reverse order
    """
    entries = read_journal(journal_path)

    # Build map of file -> (intent, success) pairs
    file_mods: dict[str, dict] = {}

    for entry in entries:
        if entry.type == "intent":
            file_mods[entry.file] = {"intent": entry.data, "success": None}
        elif entry.type == "success":
            if entry.file in file_mods:
                file_mods[entry.file]["success"] = entry.data

    # Create revert contexts for completed modifications (reverse order)
    revert_plan = []
    for file_path, mods in file_mods.items():
        if mods["intent"] and mods["success"]:
            intent = mods["intent"]
            success = mods["success"]

            # Read full pre_image from intent (no truncation)
            pre_image_str = intent.get("pre_image", "")
            restore_content = pre_image_str.encode("utf-8", errors="surrogateescape")

            context = RevertContext(
                file=file_path,
                expected_current_sha=success["after_sha"],
                restore_content=restore_content,
                original_sha=intent["before_sha"],
                plan_id=intent["plan_id"],
                rule_ids=intent["rule_ids"]
            )
            revert_plan.append(context)

    # Reverse order (most recent first)
    return list(reversed(revert_plan))


def find_latest_journal(journal_dir: Path = Path(".ace/journals")) -> Path | None:
    """
    Find the most recent journal file by modification time.

    Args:
        journal_dir: Directory containing journal files

    Returns:
        Path to latest journal file, or None if directory is empty
    """
    if not journal_dir.exists():
        return None

    journals = list(journal_dir.glob("*.jsonl"))
    if not journals:
        return None

    # Sort by modification time (most recent first)
    journals.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return journals[0]


def get_journal_id_from_path(journal_path: Path) -> str:
    """Extract run_id from journal filename."""
    return journal_path.stem  # Remove .jsonl extension
