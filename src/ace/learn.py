"""
Self-learning module for ACE - adaptive thresholds and personal memory.

Learns from user actions (reverts, skips, allow/deny) and adapts thresholds per-repo.
No ML, just robust counters and moving averages. Offline only.

v2 enhancements:
- Per-rule success_rate, revert_rate, sample_size tracking
- Auto-skiplist patterns on 3 consecutive reverts per (rule,file)
- Weekly decay 0.8
- Tuned threshold clamped 0.60-0.85
"""

import hashlib
import json
import time
from collections import defaultdict, deque
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
MIN_SAMPLE_SIZE = 5  # Minimum sample size for threshold tuning
WEEKLY_DECAY = 0.8  # Weekly decay factor for time-based weighting
REVERT_THRESHOLD_SKIPLIST = 3  # Consecutive reverts before auto-skiplist

OutcomeType = Literal["applied", "reverted", "suggested", "skipped"]


@dataclass
class RuleStats:
    """Statistics for a single rule (v2 with enhanced tracking)."""

    applied: int = 0
    reverted: int = 0
    suggested: int = 0
    skipped: int = 0
    # v2: Track timestamps for time-weighted decay
    last_updated: float = 0.0  # Unix timestamp
    # v2: Track consecutive reverts per file for auto-skiplist
    consecutive_reverts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "reverted": self.reverted,
            "suggested": self.suggested,
            "skipped": self.skipped,
            "last_updated": self.last_updated,
            "consecutive_reverts": self.consecutive_reverts,
        }

    @staticmethod
    def from_dict(data: dict) -> "RuleStats":
        return RuleStats(
            applied=data.get("applied", 0),
            reverted=data.get("reverted", 0),
            suggested=data.get("suggested", 0),
            skipped=data.get("skipped", 0),
            last_updated=data.get("last_updated", 0.0),
            consecutive_reverts=data.get("consecutive_reverts", {}),
        )

    def total_actions(self) -> int:
        """Total number of actions (applied + reverted)."""
        return self.applied + self.reverted

    def sample_size(self) -> int:
        """Sample size for statistical significance."""
        return self.total_actions()

    def revert_rate(self) -> float:
        """Calculate revert rate (reverts / total_actions)."""
        total = self.total_actions()
        if total == 0:
            return 0.0
        return self.reverted / total

    def success_rate(self) -> float:
        """Calculate success rate (applied / total_actions)."""
        total = self.total_actions()
        if total == 0:
            return 0.0
        return self.applied / total

    def apply_rate(self) -> float:
        """Calculate apply rate (applied / total_actions) - alias for success_rate."""
        return self.success_rate()

    def apply_decay(self, weeks_elapsed: float, decay_factor: float = WEEKLY_DECAY) -> None:
        """
        Apply time-based decay to statistics.

        Args:
            weeks_elapsed: Number of weeks since last update
            decay_factor: Decay multiplier per week (default: 0.8)
        """
        if weeks_elapsed <= 0:
            return

        multiplier = decay_factor ** weeks_elapsed
        self.applied = int(self.applied * multiplier)
        self.reverted = int(self.reverted * multiplier)
        self.suggested = int(self.suggested * multiplier)
        self.skipped = int(self.skipped * multiplier)


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
    """Complete learning data structure (v2 with auto-skiplist)."""

    rules: dict[str, RuleStats] = field(default_factory=dict)
    contexts: dict[str, ContextStats] = field(default_factory=dict)
    tuning: dict[str, float] = field(default_factory=lambda: {
        "alpha": 0.7,
        "beta": 0.3,
        "min_auto": DEFAULT_MIN_AUTO,
        "min_suggest": DEFAULT_MIN_SUGGEST,
    })
    # v2: Auto-skiplist patterns (rule_id -> list of file patterns)
    auto_skiplist: dict[str, list[str]] = field(default_factory=dict)
    # Event history for moving average (not persisted, computed on-the-fly)
    _event_history: dict[str, deque] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            "rules": {rule_id: stats.to_dict() for rule_id, stats in self.rules.items()},
            "contexts": {ctx_key: stats.to_dict() for ctx_key, stats in self.contexts.items()},
            "tuning": self.tuning,
            "auto_skiplist": self.auto_skiplist,
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
        learning.auto_skiplist = data.get("auto_skiplist", {})
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

    def record_outcome(
        self, rule_id: str, outcome: OutcomeType, context_key: str | None = None, file_path: str | None = None
    ) -> None:
        """
        Record an outcome for a rule (v2 with auto-skiplist and decay).

        Args:
            rule_id: Rule identifier (e.g., "PY-E201-BROAD-EXCEPT")
            outcome: One of "applied", "reverted", "suggested", "skipped"
            context_key: Optional context key for fine-grained tracking
            file_path: Optional file path for auto-skiplist tracking
        """
        # Ensure rule stats exist
        if rule_id not in self.data.rules:
            self.data.rules[rule_id] = RuleStats()

        stats = self.data.rules[rule_id]

        # v2: Apply weekly decay before updating
        current_time = time.time()
        if stats.last_updated > 0:
            weeks_elapsed = (current_time - stats.last_updated) / (7 * 24 * 3600)
            if weeks_elapsed > 0.1:  # Only decay if > ~7 hours
                stats.apply_decay(weeks_elapsed, WEEKLY_DECAY)

        # Update timestamp
        stats.last_updated = current_time

        # Update counters
        if outcome == "applied":
            stats.applied += 1
            # Reset consecutive reverts for this file
            if file_path and file_path in stats.consecutive_reverts:
                stats.consecutive_reverts[file_path] = 0
        elif outcome == "reverted":
            stats.reverted += 1
            # v2: Track consecutive reverts for auto-skiplist
            if file_path:
                stats.consecutive_reverts[file_path] = stats.consecutive_reverts.get(file_path, 0) + 1
                # Add to auto-skiplist if threshold reached
                if stats.consecutive_reverts[file_path] >= REVERT_THRESHOLD_SKIPLIST:
                    self._add_to_auto_skiplist(rule_id, file_path)
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

    def _add_to_auto_skiplist(self, rule_id: str, file_path: str) -> None:
        """
        Add a file pattern to auto-skiplist for a rule.

        Args:
            rule_id: Rule identifier
            file_path: File path that triggered skiplist
        """
        if rule_id not in self.data.auto_skiplist:
            self.data.auto_skiplist[rule_id] = []

        # Add file pattern if not already present
        if file_path not in self.data.auto_skiplist[rule_id]:
            self.data.auto_skiplist[rule_id].append(file_path)

    def tuned_threshold(self, rule_id: str) -> float:
        """
        Calculate tuned threshold for a rule based on learning history (v2).

        Logic:
        - Start with default (0.70 for auto)
        - Require minimum sample size of 5
        - If revert rate > 25%, raise threshold by +0.05 (cap 0.85)
        - If apply rate > 80%, lower threshold by -0.05 (floor 0.60)

        Args:
            rule_id: Rule identifier

        Returns:
            Tuned threshold clamped to [0.60, 0.85]
        """
        if rule_id not in self.data.rules:
            return DEFAULT_MIN_AUTO

        stats = self.data.rules[rule_id]

        # Start with default
        min_auto = self.data.tuning.get("min_auto", DEFAULT_MIN_AUTO)

        # Calculate rates
        revert_rate = stats.revert_rate()
        success_rate = stats.success_rate()

        # v2: Only adjust if we have enough data (minimum sample size)
        if stats.sample_size() < MIN_SAMPLE_SIZE:
            return min_auto

        # High revert rate → raise threshold (be more conservative)
        if revert_rate > HIGH_REVERT_RATE:
            min_auto = min(min_auto + THRESHOLD_DELTA, CEIL_MIN_AUTO)

        # High success rate → lower threshold (be more aggressive)
        elif success_rate > HIGH_APPLY_RATE:
            min_auto = max(min_auto - THRESHOLD_DELTA, FLOOR_MIN_AUTO)

        # v2: Clamp to [0.60, 0.85]
        return max(FLOOR_MIN_AUTO, min(min_auto, CEIL_MIN_AUTO))

    def tuned_thresholds(self, rule_id: str) -> tuple[float, float]:
        """
        Calculate tuned thresholds for a rule based on learning history.

        Args:
            rule_id: Rule identifier

        Returns:
            Tuple of (min_auto_threshold, min_suggest_threshold)
        """
        min_auto = self.tuned_threshold(rule_id)
        min_suggest = self.data.tuning.get("min_suggest", DEFAULT_MIN_SUGGEST)
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

    def should_skip_file_for_rule(self, rule_id: str, file_path: str) -> bool:
        """
        Check if a file should be skipped for a rule based on auto-skiplist.

        Args:
            rule_id: Rule identifier
            file_path: File path to check

        Returns:
            True if file should be skipped for this rule
        """
        if rule_id not in self.data.auto_skiplist:
            return False

        # Check if file matches any skiplist pattern
        for pattern in self.data.auto_skiplist[rule_id]:
            if file_path == pattern:
                return True

        return False

    def get_tuned_rules(self) -> list[tuple[str, float, RuleStats]]:
        """
        Get rules with non-default tuned thresholds.

        Returns:
            List of (rule_id, tuned_threshold, stats) tuples for rules with adjustments
        """
        tuned_rules = []

        for rule_id, stats in self.data.rules.items():
            if stats.sample_size() >= MIN_SAMPLE_SIZE:
                threshold = self.tuned_threshold(rule_id)
                if abs(threshold - DEFAULT_MIN_AUTO) > 0.001:  # Has adjustment
                    tuned_rules.append((rule_id, threshold, stats))

        # Sort by threshold (most conservative first)
        tuned_rules.sort(key=lambda x: -x[1])

        return tuned_rules

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
