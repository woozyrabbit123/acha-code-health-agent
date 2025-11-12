"""
Self-learning module for ACE - adaptive thresholds and personal memory.

Learns from user actions (reverts, skips, allow/deny) and adapts thresholds per-repo.
No ML, just robust counters and moving averages. Offline only.
"""

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Threshold adjustment parameters
DEFAULT_MIN_AUTO = 0.70
DEFAULT_MIN_SUGGEST = 0.50
FLOOR_MIN_AUTO = 0.60
CEIL_MIN_AUTO = 0.85
THRESHOLD_DELTA = 0.05
HIGH_REVERT_RATE = 0.25  # 25%
HIGH_APPLY_RATE = 0.80  # 80%
WINDOW_SIZE = 20  # Look at last 20 events for rate calculation

OutcomeType = Literal["applied", "reverted", "suggested", "skipped"]


@dataclass
class RuleStats:
    """Statistics for a single rule."""

    applied: int = 0
    reverted: int = 0
    suggested: int = 0
    skipped: int = 0

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "reverted": self.reverted,
            "suggested": self.suggested,
            "skipped": self.skipped,
        }

    @staticmethod
    def from_dict(data: dict) -> "RuleStats":
        return RuleStats(
            applied=data.get("applied", 0),
            reverted=data.get("reverted", 0),
            suggested=data.get("suggested", 0),
            skipped=data.get("skipped", 0),
        )

    def total_actions(self) -> int:
        """Total number of actions (applied + reverted)."""
        return self.applied + self.reverted

    def revert_rate(self) -> float:
        """Calculate revert rate (reverts / total_actions)."""
        total = self.total_actions()
        if total == 0:
            return 0.0
        return self.reverted / total

    def apply_rate(self) -> float:
        """Calculate apply rate (applied / total_actions)."""
        total = self.total_actions()
        if total == 0:
            return 0.0
        return self.applied / total


@dataclass
class ContextStats:
    """Statistics for a specific context (file + pack + snippet)."""

    hits: int = 0
    reverts: int = 0

    def to_dict(self) -> dict:
        return {"hits": self.hits, "reverts": self.reverts}

    @staticmethod
    def from_dict(data: dict) -> "ContextStats":
        return ContextStats(
            hits=data.get("hits", 0),
            reverts=data.get("reverts", 0),
        )

    def revert_rate(self) -> float:
        """Calculate revert rate for this context."""
        if self.hits == 0:
            return 0.0
        return self.reverts / self.hits


@dataclass
class LearningData:
    """Complete learning data structure."""

    rules: dict[str, RuleStats] = field(default_factory=dict)
    contexts: dict[str, ContextStats] = field(default_factory=dict)
    tuning: dict[str, float] = field(default_factory=lambda: {
        "alpha": 0.7,
        "beta": 0.3,
        "min_auto": DEFAULT_MIN_AUTO,
        "min_suggest": DEFAULT_MIN_SUGGEST,
    })
    # Event history for moving average (not persisted, computed on-the-fly)
    _event_history: dict[str, deque] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            "rules": {rule_id: stats.to_dict() for rule_id, stats in self.rules.items()},
            "contexts": {ctx_key: stats.to_dict() for ctx_key, stats in self.contexts.items()},
            "tuning": self.tuning,
        }

    @staticmethod
    def from_dict(data: dict) -> "LearningData":
        learning = LearningData()
        learning.rules = {
            rule_id: RuleStats.from_dict(stats_dict)
            for rule_id, stats_dict in data.get("rules", {}).items()
        }
        learning.contexts = {
            ctx_key: ContextStats.from_dict(stats_dict)
            for ctx_key, stats_dict in data.get("contexts", {}).items()
        }
        learning.tuning = data.get("tuning", {
            "alpha": 0.7,
            "beta": 0.3,
            "min_auto": DEFAULT_MIN_AUTO,
            "min_suggest": DEFAULT_MIN_SUGGEST,
        })
        return learning


class LearningEngine:
    """
    Self-learning engine for ACE.

    Tracks outcomes and adapts thresholds based on user actions.
    """

    def __init__(self, learn_path: Path = Path(".ace/learn.json")):
        self.learn_path = learn_path
        self.data = LearningData()

    def load(self) -> None:
        """Load learning data from disk."""
        if not self.learn_path.exists():
            self.data = LearningData()
            return

        try:
            with open(self.learn_path, "r", encoding="utf-8") as f:
                data_dict = json.load(f)
            self.data = LearningData.from_dict(data_dict)
        except (json.JSONDecodeError, OSError):
            # If corrupted, start fresh
            self.data = LearningData()

    def save(self) -> None:
        """Save learning data to disk with deterministic serialization."""
        # Ensure parent directory exists
        self.learn_path.parent.mkdir(parents=True, exist_ok=True)

        # Write with deterministic formatting
        with open(self.learn_path, "w", encoding="utf-8") as f:
            json.dump(self.data.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")  # Trailing newline

    def record_outcome(self, rule_id: str, outcome: OutcomeType, context_key: str | None = None) -> None:
        """
        Record an outcome for a rule.

        Args:
            rule_id: Rule identifier (e.g., "PY-E201-BROAD-EXCEPT")
            outcome: One of "applied", "reverted", "suggested", "skipped"
            context_key: Optional context key for fine-grained tracking
        """
        # Ensure rule stats exist
        if rule_id not in self.data.rules:
            self.data.rules[rule_id] = RuleStats()

        stats = self.data.rules[rule_id]

        # Update counters
        if outcome == "applied":
            stats.applied += 1
        elif outcome == "reverted":
            stats.reverted += 1
        elif outcome == "suggested":
            stats.suggested += 1
        elif outcome == "skipped":
            stats.skipped += 1

        # Track context if provided
        if context_key:
            if context_key not in self.data.contexts:
                self.data.contexts[context_key] = ContextStats()

            ctx_stats = self.data.contexts[context_key]
            ctx_stats.hits += 1
            if outcome == "reverted":
                ctx_stats.reverts += 1

        # Save after each update
        self.save()

    def tuned_thresholds(self, rule_id: str) -> tuple[float, float]:
        """
        Calculate tuned thresholds for a rule based on learning history.

        Logic:
        - Start with defaults (0.70 for auto, 0.50 for suggest)
        - If revert rate > 25% over last actions, raise min_auto by +0.05 (cap 0.85)
        - If apply rate > 80% over last actions, lower min_auto by -0.05 (floor 0.60)

        Args:
            rule_id: Rule identifier

        Returns:
            Tuple of (min_auto_threshold, min_suggest_threshold)
        """
        if rule_id not in self.data.rules:
            return (DEFAULT_MIN_AUTO, DEFAULT_MIN_SUGGEST)

        stats = self.data.rules[rule_id]

        # Start with defaults
        min_auto = self.data.tuning.get("min_auto", DEFAULT_MIN_AUTO)
        min_suggest = self.data.tuning.get("min_suggest", DEFAULT_MIN_SUGGEST)

        # Calculate rates (using all history, not windowed for simplicity)
        revert_rate = stats.revert_rate()
        apply_rate = stats.apply_rate()

        # Only adjust if we have enough data (at least 5 actions)
        total_actions = stats.total_actions()
        if total_actions < 5:
            return (min_auto, min_suggest)

        # High revert rate → raise threshold (be more conservative)
        if revert_rate > HIGH_REVERT_RATE:
            min_auto = min(min_auto + THRESHOLD_DELTA, CEIL_MIN_AUTO)

        # High apply rate → lower threshold (be more aggressive)
        elif apply_rate > HIGH_APPLY_RATE:
            min_auto = max(min_auto - THRESHOLD_DELTA, FLOOR_MIN_AUTO)

        return (min_auto, min_suggest)

    def should_skip_context(self, context_key: str, threshold: float = 0.5) -> bool:
        """
        Check if a context should be skipped based on learning history.

        Args:
            context_key: Context identifier
            threshold: Revert rate threshold for skipping (default: 0.5 = 50%)

        Returns:
            True if context should be skipped
        """
        if context_key not in self.data.contexts:
            return False

        ctx_stats = self.data.contexts[context_key]

        # Need at least 3 hits to make a decision
        if ctx_stats.hits < 3:
            return False

        return ctx_stats.revert_rate() > threshold

    def get_top_rules_by_revert_rate(self, limit: int = 10) -> list[tuple[str, RuleStats, float]]:
        """
        Get top rules by revert rate.

        Args:
            limit: Maximum number of rules to return

        Returns:
            List of (rule_id, stats, revert_rate) tuples, sorted by revert rate descending
        """
        rules_with_rates = []

        for rule_id, stats in self.data.rules.items():
            # Only include rules with at least 2 actions
            if stats.total_actions() >= 2:
                revert_rate = stats.revert_rate()
                rules_with_rates.append((rule_id, stats, revert_rate))

        # Sort by revert rate descending
        rules_with_rates.sort(key=lambda x: x[2], reverse=True)

        return rules_with_rates[:limit]

    def reset(self) -> None:
        """Reset all learning data."""
        self.data = LearningData()
        if self.learn_path.exists():
            self.learn_path.unlink()


def context_key(plan) -> str:
    """
    Generate a context key for a plan.

    Context = file + rule + snippet_hash (first 100 chars of first finding)

    Args:
        plan: EditPlan object

    Returns:
        Context key string
    """
    if not plan.findings:
        return "no-findings"

    first_finding = plan.findings[0]
    file_path = first_finding.file
    rule_id = first_finding.rule

    # Get snippet (first 100 chars for hashing)
    snippet = first_finding.snippet[:100] if first_finding.snippet else ""
    snippet_hash = hashlib.sha256(snippet.encode()).hexdigest()[:8]

    return f"{file_path}:{rule_id}:{snippet_hash}"


def get_rule_ids_from_plan(plan) -> list[str]:
    """
    Extract rule IDs from a plan.

    Args:
        plan: EditPlan object

    Returns:
        List of unique rule IDs
    """
    if not plan.findings:
        return []

    rule_ids = list(set(finding.rule for finding in plan.findings))
    return rule_ids
