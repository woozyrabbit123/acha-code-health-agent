"""
Performance telemetry for ACE - track rule execution times.

Lightweight timers that write to .ace/telemetry.jsonl for performance analysis.

v2 enhancements:
- Append JSONL {rule_id, ms, files, ok, reverted} per execution
- summary(days=7) aggregates mean, p95, count
"""

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class RuleTiming:
    """Timing data for a single rule execution (v2 with extended metadata)."""

    rule_id: str
    duration_ms: float
    timestamp: float
    files: int = 0  # v2: Number of files processed
    ok: bool = True  # v2: Execution succeeded
    reverted: bool = False  # v2: Was this execution reverted


@dataclass
class TelemetryStats:
    """Aggregated telemetry statistics (v2 with p95)."""

    per_rule_avg_ms: dict[str, float] = field(default_factory=dict)
    per_rule_p95_ms: dict[str, float] = field(default_factory=dict)  # v2
    per_rule_count: dict[str, int] = field(default_factory=dict)
    total_executions: int = 0


class Telemetry:
    """
    Telemetry tracker for rule execution performance.

    Records timing data to .ace/telemetry.jsonl in append-only mode.
    """

    def __init__(self, telemetry_path: Path = Path(".ace/telemetry.jsonl")):
        self.telemetry_path = telemetry_path
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure parent directory exists."""
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        rule_id: str,
        duration_ms: float,
        files: int = 0,
        ok: bool = True,
        reverted: bool = False,
    ) -> None:
        """
        Record a rule execution timing (v2 with extended metadata).

        Args:
            rule_id: Rule identifier (e.g., "PY-S101-UNSAFE-HTTP")
            duration_ms: Execution duration in milliseconds
            files: Number of files processed (v2)
            ok: Execution succeeded (v2)
            reverted: Was this execution reverted (v2)
        """
        # Create timing entry
        timing = RuleTiming(
            rule_id=rule_id,
            duration_ms=duration_ms,
            timestamp=time.time(),
            files=files,
            ok=ok,
            reverted=reverted,
        )

        # Write to JSONL (append mode) with v2 fields
        with open(self.telemetry_path, "a", encoding="utf-8") as f:
            entry = {
                "rule_id": timing.rule_id,
                "ms": timing.duration_ms,  # v2: renamed from duration_ms for brevity
                "timestamp": timing.timestamp,
                "files": timing.files,
                "ok": timing.ok,
                "reverted": timing.reverted,
            }
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def load_stats(self, days: int | None = None) -> TelemetryStats:
        """
        Load and aggregate telemetry statistics (v2 with p95).

        Args:
            days: Optional filter for last N days (None = all time)

        Returns:
            TelemetryStats with per-rule averages, p95, and counts
        """
        stats = TelemetryStats()

        if not self.telemetry_path.exists():
            return stats

        # v2: Time filter
        cutoff_time = None
        if days is not None:
            cutoff_time = time.time() - (days * 24 * 3600)

        # Accumulators for averaging and p95
        total_durations: dict[str, float] = {}
        all_durations: dict[str, list[float]] = {}  # v2: For p95 calculation
        counts: dict[str, int] = {}

        try:
            with open(self.telemetry_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        rule_id = entry["rule_id"]
                        # Handle both old and new format
                        duration_ms = entry.get("ms", entry.get("duration_ms", 0))
                        timestamp = entry.get("timestamp", 0)

                        # v2: Apply time filter
                        if cutoff_time is not None and timestamp < cutoff_time:
                            continue

                        # Accumulate
                        if rule_id not in total_durations:
                            total_durations[rule_id] = 0.0
                            all_durations[rule_id] = []
                            counts[rule_id] = 0

                        total_durations[rule_id] += duration_ms
                        all_durations[rule_id].append(duration_ms)
                        counts[rule_id] += 1
                        stats.total_executions += 1

                    except (json.JSONDecodeError, KeyError):
                        # Skip malformed lines
                        continue

        except OSError:
            # If file can't be read, return empty stats
            return stats

        # Calculate averages and p95
        for rule_id in total_durations:
            if counts[rule_id] > 0:
                stats.per_rule_avg_ms[rule_id] = total_durations[rule_id] / counts[rule_id]
                stats.per_rule_count[rule_id] = counts[rule_id]

                # v2: Calculate p95
                durations = sorted(all_durations[rule_id])
                p95_index = int(len(durations) * 0.95)
                if p95_index >= len(durations):
                    p95_index = len(durations) - 1
                stats.per_rule_p95_ms[rule_id] = durations[p95_index] if durations else 0.0

        return stats

    def summary(self, days: int = 7) -> TelemetryStats:
        """
        Get summary statistics for the last N days.

        Args:
            days: Number of days to aggregate (default: 7)

        Returns:
            TelemetryStats with mean, p95, and count per rule
        """
        return self.load_stats(days=days)

    def get_top_slow_rules(self, limit: int = 10) -> list[tuple[str, float, int]]:
        """
        Get top slowest rules by average execution time.

        Args:
            limit: Maximum number of rules to return

        Returns:
            List of (rule_id, avg_ms, count) tuples, sorted by avg_ms descending
        """
        stats = self.load_stats()

        rules_with_times = [
            (rule_id, avg_ms, stats.per_rule_count[rule_id])
            for rule_id, avg_ms in stats.per_rule_avg_ms.items()
        ]

        # Sort by average time descending
        rules_with_times.sort(key=lambda x: x[1], reverse=True)

        return rules_with_times[:limit]

    def clear(self) -> None:
        """Clear all telemetry data."""
        if self.telemetry_path.exists():
            self.telemetry_path.unlink()


@contextmanager
def time_block(rule_id: str, telemetry: Telemetry | None = None):
    """
    Context manager for timing a code block.

    Usage:
        with time_block("PY-S201-SUBPROCESS-CHECK"):
            # ... rule execution ...
            pass

    Args:
        rule_id: Rule identifier
        telemetry: Optional Telemetry instance (if None, creates default)
    """
    if telemetry is None:
        telemetry = Telemetry()

    start_time = time.perf_counter()
    try:
        yield
    finally:
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000.0
        telemetry.record(rule_id, duration_ms)


def get_cost_ms_rank(rule_ids: list[str]) -> dict[str, int]:
    """
    Get rank of rules by cost (cheaper = lower rank).

    Args:
        rule_ids: List of rule IDs to rank

    Returns:
        Dictionary mapping rule_id to rank (0-based, 0 = fastest)
    """
    telemetry = Telemetry()
    stats = telemetry.load_stats()

    # Get average times for rules (default to 0 if no data)
    rule_times = [
        (rule_id, stats.per_rule_avg_ms.get(rule_id, 0.0))
        for rule_id in rule_ids
    ]

    # Sort by time ascending (cheaper first)
    rule_times.sort(key=lambda x: x[1])

    # Create rank mapping
    ranks = {rule_id: rank for rank, (rule_id, _) in enumerate(rule_times)}

    return ranks
