"""Performance profiling utilities for ACE."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PhaseTimer:
    """Timer for a single execution phase."""

    name: str
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float | None = None
    duration_ms: int | None = None

    def stop(self) -> int:
        """
        Stop the timer and return duration in milliseconds.

        Returns:
            Duration in milliseconds
        """
        self.end_time = time.perf_counter()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
        return self.duration_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert timer to dictionary."""
        return {
            "phase": self.name,
            "duration_ms": self.duration_ms or 0,
        }


@dataclass
class RuleTimer:
    """Timer for individual rule execution."""

    rule_id: str
    file_count: int = 0
    total_duration_ms: int = 0

    def add_duration(self, duration_ms: int):
        """Add duration to total."""
        self.file_count += 1
        self.total_duration_ms += duration_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert timer to dictionary."""
        return {
            "rule": self.rule_id,
            "file_count": self.file_count,
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": self.total_duration_ms // self.file_count if self.file_count > 0 else 0,
        }


class PerformanceProfiler:
    """
    Performance profiler for ACE operations.

    Tracks phase timings and per-rule execution statistics.
    """

    def __init__(self):
        """Initialize profiler."""
        self.phases: dict[str, PhaseTimer] = {}
        self.rules: dict[str, RuleTimer] = {}
        self.enabled = False

    def enable(self):
        """Enable profiling."""
        self.enabled = True

    def start_phase(self, name: str) -> PhaseTimer:
        """
        Start timing a phase.

        Args:
            name: Phase name

        Returns:
            PhaseTimer instance
        """
        if not self.enabled:
            return PhaseTimer(name)

        timer = PhaseTimer(name)
        self.phases[name] = timer
        return timer

    def stop_phase(self, name: str) -> int:
        """
        Stop timing a phase.

        Args:
            name: Phase name

        Returns:
            Duration in milliseconds (0 if phase not found)
        """
        if not self.enabled or name not in self.phases:
            return 0

        return self.phases[name].stop()

    def record_rule(self, rule_id: str, duration_ms: int):
        """
        Record rule execution time.

        Args:
            rule_id: Rule identifier
            duration_ms: Execution duration in milliseconds
        """
        if not self.enabled:
            return

        if rule_id not in self.rules:
            self.rules[rule_id] = RuleTimer(rule_id)

        self.rules[rule_id].add_duration(duration_ms)

    def to_dict(self) -> dict[str, Any]:
        """
        Export profile to dictionary.

        Returns:
            Profile dictionary with sorted keys
        """
        phases_list = [timer.to_dict() for timer in self.phases.values()]
        phases_list.sort(key=lambda p: p["phase"])

        rules_list = [timer.to_dict() for timer in self.rules.values()]
        rules_list.sort(key=lambda r: r["total_duration_ms"], reverse=True)

        return {
            "phases": phases_list,
            "rules": rules_list,
            "total_duration_ms": sum(p["duration_ms"] for p in phases_list),
        }

    def save(self, output_path: str | Path):
        """
        Save profile to JSON file.

        Args:
            output_path: Output file path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")


# Global profiler instance (singleton pattern)
_global_profiler: PerformanceProfiler | None = None


def get_profiler() -> PerformanceProfiler:
    """
    Get global profiler instance.

    Returns:
        PerformanceProfiler instance
    """
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler


def reset_profiler():
    """Reset global profiler."""
    global _global_profiler
    _global_profiler = PerformanceProfiler()
