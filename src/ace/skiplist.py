"""Learning skiplist - Learn from user reverts to avoid repeat suggestions."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace.safety import atomic_write
from ace.skills.python import EditPlan
from ace.uir import UnifiedIssue


@dataclass
class SkipEntry:
    """
    A skiplist entry representing a rejected fix.

    Attributes:
        key: Stable key (rule + content hash + context)
        rule_id: Rule identifier
        context_path: Context path (file::class::func)
        content_hash: Short hash of the content snippet
        timestamp: When this was added
        reason: Reason for skip (e.g., "reverted", "user-skip")
    """

    key: str
    rule_id: str
    context_path: str
    content_hash: str
    timestamp: str
    reason: str = "reverted"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "key": self.key,
            "rule_id": self.rule_id,
            "context_path": self.context_path,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SkipEntry":
        """Create SkipEntry from dictionary."""
        return SkipEntry(
            key=d["key"],
            rule_id=d["rule_id"],
            context_path=d["context_path"],
            content_hash=d["content_hash"],
            timestamp=d["timestamp"],
            reason=d.get("reason", "reverted"),
        )


class Skiplist:
    """
    Learning skiplist - tracks rejected fixes to avoid repeat suggestions.

    The skiplist persists as .ace/skiplist.json and grows over time as the user
    reverts changes or explicitly skips suggestions.
    """

    def __init__(self, skiplist_path: Path | str = ".ace/skiplist.json"):
        """
        Initialize skiplist.

        Args:
            skiplist_path: Path to skiplist JSON file
        """
        self.skiplist_path = Path(skiplist_path)
        self.entries: dict[str, SkipEntry] = {}
        self.load()

    def load(self) -> None:
        """Load skiplist from disk."""
        if not self.skiplist_path.exists():
            return

        try:
            with open(self.skiplist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.entries = {
                    key: SkipEntry.from_dict(entry)
                    for key, entry in data.items()
                }
        except Exception:
            # Ignore errors, start fresh
            self.entries = {}

    def save(self) -> None:
        """Save skiplist to disk with atomic write for durability."""
        # Serialize entries
        data = {key: entry.to_dict() for key, entry in self.entries.items()}

        # Write atomically with fsync for durability
        content = json.dumps(data, indent=2, sort_keys=True).encode('utf-8')
        atomic_write(self.skiplist_path, content)

    def compute_key(
        self,
        rule_id: str,
        content: str,
        context_path: str,
    ) -> str:
        """
        Compute stable key for a finding.

        Args:
            rule_id: Rule identifier
            content: Code content/snippet
            context_path: Context path (file::class::func)

        Returns:
            Stable key (first 16 chars of SHA256)
        """
        # Hash the content to get a short identifier
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]

        # Combine rule, content hash, and context
        combined = f"{rule_id}::{content_hash}::{context_path}"
        key_hash = hashlib.sha256(combined.encode("utf-8")).digest()

        return key_hash.hex()[:16]

    def add(
        self,
        rule_id: str,
        content: str,
        context_path: str,
        reason: str = "reverted",
    ) -> str:
        """
        Add an entry to the skiplist.

        Args:
            rule_id: Rule identifier
            content: Code content/snippet
            context_path: Context path
            reason: Reason for skip

        Returns:
            The skip key that was added
        """
        key = self.compute_key(rule_id, content, context_path)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]

        from datetime import datetime
        timestamp = datetime.utcnow().isoformat() + "Z"

        entry = SkipEntry(
            key=key,
            rule_id=rule_id,
            context_path=context_path,
            content_hash=content_hash,
            timestamp=timestamp,
            reason=reason,
        )

        self.entries[key] = entry
        self.save()

        return key

    def should_skip(
        self,
        rule_id: str,
        content: str,
        context_path: str,
    ) -> bool:
        """
        Check if a finding should be skipped.

        Args:
            rule_id: Rule identifier
            content: Code content/snippet
            context_path: Context path

        Returns:
            True if should skip, False otherwise
        """
        key = self.compute_key(rule_id, content, context_path)
        return key in self.entries

    def should_skip_finding(self, finding: UnifiedIssue) -> bool:
        """
        Check if a finding should be skipped.

        Args:
            finding: UnifiedIssue to check

        Returns:
            True if should skip, False otherwise
        """
        # Use file as context for now (could be enhanced with AST analysis)
        context_path = finding.file
        content = finding.snippet if finding.snippet else ""

        return self.should_skip(finding.rule, content, context_path)

    def should_skip_plan(self, plan: EditPlan) -> bool:
        """
        Check if an EditPlan should be skipped.

        Args:
            plan: EditPlan to check

        Returns:
            True if any finding in the plan should be skipped
        """
        return any(self.should_skip_finding(f) for f in plan.findings)

    def filter_findings(
        self,
        findings: list[UnifiedIssue],
    ) -> tuple[list[UnifiedIssue], list[UnifiedIssue]]:
        """
        Filter findings based on skiplist.

        Args:
            findings: List of UnifiedIssue findings

        Returns:
            Tuple of (kept_findings, skipped_findings)
        """
        kept = []
        skipped = []

        for finding in findings:
            if self.should_skip_finding(finding):
                skipped.append(finding)
            else:
                kept.append(finding)

        return kept, skipped

    def filter_plans(
        self,
        plans: list[EditPlan],
    ) -> tuple[list[EditPlan], list[EditPlan]]:
        """
        Filter plans based on skiplist.

        Args:
            plans: List of EditPlan objects

        Returns:
            Tuple of (kept_plans, skipped_plans)
        """
        kept = []
        skipped = []

        for plan in plans:
            if self.should_skip_plan(plan):
                skipped.append(plan)
            else:
                kept.append(plan)

        return kept, skipped

    def remove(self, key: str) -> bool:
        """
        Remove an entry from the skiplist.

        Args:
            key: Skip key to remove

        Returns:
            True if removed, False if not found
        """
        if key in self.entries:
            del self.entries[key]
            self.save()
            return True
        return False

    def clear(self) -> int:
        """
        Clear all entries from the skiplist.

        Returns:
            Number of entries cleared
        """
        count = len(self.entries)
        self.entries = {}
        self.save()
        return count

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary statistics.

        Returns:
            Dictionary with skiplist statistics
        """
        # Count by rule
        rule_counts: dict[str, int] = {}
        for entry in self.entries.values():
            rule_counts[entry.rule_id] = rule_counts.get(entry.rule_id, 0) + 1

        # Count by reason
        reason_counts: dict[str, int] = {}
        for entry in self.entries.values():
            reason_counts[entry.reason] = reason_counts.get(entry.reason, 0) + 1

        return {
            "total_entries": len(self.entries),
            "rules": sorted(rule_counts.items(), key=lambda x: -x[1]),
            "reasons": sorted(reason_counts.items(), key=lambda x: -x[1]),
        }


def add_plan_to_skiplist(
    plan: EditPlan,
    skiplist: Skiplist,
    reason: str = "reverted",
) -> list[str]:
    """
    Add all findings from a plan to the skiplist.

    Args:
        plan: EditPlan that was reverted/skipped
        skiplist: Skiplist instance
        reason: Reason for skip

    Returns:
        List of skip keys that were added
    """
    keys = []

    for finding in plan.findings:
        context_path = finding.file
        content = finding.snippet if finding.snippet else finding.message

        key = skiplist.add(
            rule_id=finding.rule,
            content=content,
            context_path=context_path,
            reason=reason,
        )
        keys.append(key)

    return keys


def add_pack_to_skiplist(
    pack_id: str,
    findings: list[UnifiedIssue],
    skiplist: Skiplist,
    reason: str = "pack-skipped",
) -> list[str]:
    """
    Add all findings from a pack to the skiplist.

    Args:
        pack_id: Pack identifier
        findings: List of findings in the pack
        skiplist: Skiplist instance
        reason: Reason for skip

    Returns:
        List of skip keys that were added
    """
    keys = []

    for finding in findings:
        context_path = finding.file
        content = finding.snippet if finding.snippet else finding.message

        key = skiplist.add(
            rule_id=finding.rule,
            content=content,
            context_path=context_path,
            reason=f"{reason}::{pack_id}",
        )
        keys.append(key)

    return keys
