"""Storage and persistence for baselines, receipts, and analysis cache."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class AnalysisCache:
    """
    SQLite-based analysis cache for deterministic memoization.

    The cache stores analysis results keyed by file content hash (sha256)
    and ruleset configuration hash. This enables pure memoization - cache
    hits produce byte-identical outputs to cache misses.
    """

    def __init__(self, cache_dir: str | Path = ".ace", ttl: int = 3600):
        """
        Initialize analysis cache.

        Args:
            cache_dir: Directory for cache database (default: .ace)
            ttl: Time-to-live in seconds (default: 3600)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "cache.db"
        self.ttl = ttl
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    ruleset TEXT NOT NULL,
                    findings_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (path, sha256, ruleset)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get(self, file_path: str, content_hash: str, ruleset_hash: str) -> list[dict] | None:
        """
        Retrieve cached analysis results.

        Args:
            file_path: File path (for cache key)
            content_hash: SHA256 hash of file content
            ruleset_hash: Hash of enabled rules + ACE version

        Returns:
            List of finding dicts if cache hit and not expired, None otherwise
        """
        conn = sqlite3.connect(self.cache_path)
        try:
            cursor = conn.execute(
                """
                SELECT findings_json, created_at
                FROM cache_entries
                WHERE path = ? AND sha256 = ? AND ruleset = ?
                """,
                (file_path, content_hash, ruleset_hash),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            findings_json, created_at = row

            # Check TTL
            if self.ttl > 0 and (time.time() - created_at) > self.ttl:
                return None

            # Parse and return findings
            return json.loads(findings_json)
        finally:
            conn.close()

    def set(self, file_path: str, content_hash: str, ruleset_hash: str, findings: list[dict]):
        """
        Store analysis results in cache.

        Args:
            file_path: File path (for cache key)
            content_hash: SHA256 hash of file content
            ruleset_hash: Hash of enabled rules + ACE version
            findings: List of finding dicts (must be deterministically serializable)
        """
        conn = sqlite3.connect(self.cache_path)
        try:
            # Deterministic JSON serialization (sorted keys, no whitespace)
            findings_json = json.dumps(findings, sort_keys=True, separators=(',', ':'))

            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (path, sha256, ruleset, findings_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (file_path, content_hash, ruleset_hash, findings_json, int(time.time())),
            )
            conn.commit()
        finally:
            conn.close()

    def clear(self):
        """Clear all cache entries."""
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM cache_entries")
            conn.commit()
        finally:
            conn.close()

    def invalidate_file(self, file_path: str):
        """
        Invalidate all cache entries for a specific file.

        Args:
            file_path: File path to invalidate
        """
        conn = sqlite3.connect(self.cache_path)
        try:
            conn.execute("DELETE FROM cache_entries WHERE path = ?", (file_path,))
            conn.commit()
        finally:
            conn.close()


def compute_file_hash(content: str | bytes) -> str:
    """
    Compute SHA256 hash of file content.

    Args:
        content: File content (str or bytes)

    Returns:
        SHA256 hash as hex string
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def compute_ruleset_hash(enabled_rules: list[str], ace_version: str) -> str:
    """
    Compute hash of ruleset configuration.

    This includes enabled rule IDs and ACE version to ensure cache
    invalidation when rules or analysis logic changes.

    Args:
        enabled_rules: Sorted list of enabled rule IDs
        ace_version: ACE version string

    Returns:
        SHA256 hash as hex string
    """
    # Deterministic representation: sorted rules + version
    ruleset_str = json.dumps({
        "rules": sorted(enabled_rules),
        "version": ace_version
    }, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(ruleset_str.encode("utf-8")).hexdigest()


class BaselineStore:
    """
    Baseline storage with deterministic IDs.

    Placeholder for baseline management.
    """

    pass


def save_baseline(findings: list[dict[str, Any]], output_path: str | Path) -> bool:
    """
    Save baseline snapshot as deterministic JSON.

    Args:
        findings: List of finding dicts with stable_id
        output_path: Baseline file path

    Returns:
        True if successful
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort findings by stable_id for determinism
    sorted_findings = sorted(findings, key=lambda f: f.get("stable_id", ""))

    # Extract baseline fields (stable_id, rule, severity, file, message)
    baseline_entries = [
        {
            "stable_id": f.get("stable_id", ""),
            "rule": f.get("rule", ""),
            "severity": f.get("severity", ""),
            "file": f.get("file", ""),
            "message": f.get("message", ""),
        }
        for f in sorted_findings
    ]

    # Write deterministic JSON
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(baseline_entries, fp, indent=2, sort_keys=True)
        fp.write("\n")  # Trailing newline

    return True


def load_baseline(baseline_path: str | Path) -> list[dict[str, Any]]:
    """
    Load baseline from JSON file.

    Args:
        baseline_path: Path to baseline file

    Returns:
        List of baseline entry dicts
    """
    baseline_path = Path(baseline_path)

    if not baseline_path.exists():
        return []

    with open(baseline_path, encoding="utf-8") as fp:
        return json.load(fp)


def compare_baseline(
    current_findings: list[dict[str, Any]], baseline_path: str | Path
) -> dict[str, Any]:
    """
    Compare current findings against baseline.

    Args:
        current_findings: Current finding dicts with stable_id
        baseline_path: Path to baseline file

    Returns:
        Comparison result with added/removed/changed/existing
    """
    baseline = load_baseline(baseline_path)

    # Build maps by stable_id
    baseline_map = {entry["stable_id"]: entry for entry in baseline}
    current_map = {f["stable_id"]: f for f in current_findings}

    baseline_ids = set(baseline_map.keys())
    current_ids = set(current_map.keys())

    # Compute differences
    added_ids = current_ids - baseline_ids
    removed_ids = baseline_ids - current_ids
    common_ids = baseline_ids & current_ids

    # Check for severity or message changes in common findings
    changed = []
    for stable_id in common_ids:
        baseline_entry = baseline_map[stable_id]
        current_entry = current_map[stable_id]

        if (baseline_entry["severity"] != current_entry["severity"] or
            baseline_entry["message"] != current_entry["message"]):
            changed.append({
                "stable_id": stable_id,
                "baseline": baseline_entry,
                "current": current_entry,
            })

    return {
        "added": [current_map[sid] for sid in sorted(added_ids)],
        "removed": [baseline_map[sid] for sid in sorted(removed_ids)],
        "changed": sorted(changed, key=lambda x: x["stable_id"]),
        "existing": [current_map[sid] for sid in sorted(common_ids - {c["stable_id"] for c in changed})],
    }
