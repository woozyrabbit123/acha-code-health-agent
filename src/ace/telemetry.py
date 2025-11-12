"""
Performance telemetry for ACE - track rule execution times.

Lightweight timers that write to .ace/telemetry.jsonl for performance analysis.
"""

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RuleTiming:
    """Timing data for a single rule execution."""

    rule_id: str
    duration_ms: float
    timestamp: float


@dataclass
class TelemetryStats:
    """Aggregated telemetry statistics."""

    per_rule_avg_ms: dict[str, float] = field(default_factory=dict)
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

    def record(self, rule_id: str, duration_ms: float) -> None:
        """
        Record a rule execution timing.

        Args:
            rule_id: Rule identifier (e.g., "PY-S101-UNSAFE-HTTP")
            duration_ms: Execution duration in milliseconds
        """
        # Create timing entry
        timing = RuleTiming(
            rule_id=rule_id,
            duration_ms=duration_ms,
            timestamp=time.time()
        )

        # Write to JSONL (append mode)
        with open(self.telemetry_path, "a", encoding="utf-8") as f:
            entry = {
                "rule_id": timing.rule_id,
                "duration_ms": timing.duration_ms,
                "timestamp": timing.timestamp
            }
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def load_stats(self) -> TelemetryStats:
        """
        Load and aggregate telemetry statistics.

        Returns:
            TelemetryStats with per-rule averages and counts
        """
        stats = TelemetryStats()

        if not self.telemetry_path.exists():
            return stats

        # Accumulators for averaging
        total_durations: dict[str, float] = {}
        counts: dict[str, int] = {}

        try:
            with open(self.telemetry_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        rule_id = entry["rule_id"]
                        duration_ms = entry["duration_ms"]

                        # Accumulate
                        if rule_id not in total_durations:
                            total_durations[rule_id] = 0.0
                            counts[rule_id] = 0

                        total_durations[rule_id] += duration_ms
                        counts[rule_id] += 1
                        stats.total_executions += 1

                    except (json.JSONDecodeError, KeyError):
                        # Skip malformed lines
                        continue

        except OSError:
            # If file can't be read, return empty stats
            return stats

        # Calculate averages
        for rule_id in total_durations:
            if counts[rule_id] > 0:
                stats.per_rule_avg_ms[rule_id] = total_durations[rule_id] / counts[rule_id]
                stats.per_rule_count[rule_id] = counts[rule_id]

        return stats

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
