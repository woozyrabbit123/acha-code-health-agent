"""ACE Planner v1 - Deterministic action prioritization and ordering.

Policy-driven planner using RepoMap, DepGraph, Learning, and Telemetry to
intelligently order refactoring actions.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ace.budget import compute_plan_rstar
from ace.learn import LearningEngine, context_key, get_rule_ids_from_plan
from ace.skills.python import EditPlan
from ace.telemetry import Telemetry, get_cost_ms_rank
from ace.uir import UnifiedIssue

# Try to import context engine components (optional)
try:
    from ace.context_rank import ContextRanker
    from ace.depgraph import DepGraph
    from ace.repomap import RepoMap

    CONTEXT_ENGINE_AVAILABLE = True
except ImportError:
    CONTEXT_ENGINE_AVAILABLE = False


@dataclass
class Action:
    """Planned action with priority and rationale."""

    plan: EditPlan
    priority: float
    rationale: str  # Brief explanation of why this action was prioritized
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerConfig:
    """Configuration for planner."""

    target: Path
    use_context_engine: bool = True
    use_learning: bool = True
    use_telemetry: bool = True
    max_actions: int | None = None  # Budget constraint


class Planner:
    """
    Deterministic action planner for ACE.

    Priority formula:
        priority = 100*R★ + 20*cohesion - cost_rank - revert_penalty + context_boost
    """

    def __init__(self, cfg: PlannerConfig):
        self.cfg = cfg

        # Initialize components
        self.learning = LearningEngine() if cfg.use_learning else None
        if self.learning:
            self.learning.load()

        self.telemetry = Telemetry() if cfg.use_telemetry else None

        # Context engine (optional)
        self.repo_map = None
        self.context_ranker = None
        self.depgraph = None

        if cfg.use_context_engine and CONTEXT_ENGINE_AVAILABLE:
            try:
                self.repo_map = RepoMap()
                self.repo_map.load()
                self.context_ranker = ContextRanker(self.repo_map)
                self.depgraph = DepGraph(self.repo_map)
            except Exception:
                # Context engine unavailable
                pass

    def plan_actions(self, plans: list[EditPlan]) -> list[Action]:
        """
        Plan and prioritize actions from edit plans.

        Args:
            plans: List of EditPlan objects

        Returns:
            Ordered list of Action objects with priorities and rationales
        """
        if not plans:
            return []

        # Get all unique rule IDs for cost ranking
        all_rule_ids = []
        for plan in plans:
            all_rule_ids.extend(get_rule_ids_from_plan(plan))
        all_rule_ids = list(set(all_rule_ids))

        # Get cost ranking from telemetry
        cost_ranks = {}
        if self.telemetry:
            cost_ranks = get_cost_ms_rank(all_rule_ids)

        # Calculate priority for each plan
        actions = []
        for plan in plans:
            priority, rationale = self._calculate_priority(plan, cost_ranks)
            action = Action(
                plan=plan,
                priority=priority,
                rationale=rationale,
                metadata={
                    "rule_ids": get_rule_ids_from_plan(plan),
                    "estimated_risk": plan.estimated_risk,
                },
            )
            actions.append(action)

        # Sort by priority descending, then by plan ID for determinism
        actions.sort(key=lambda a: (-a.priority, a.plan.id))

        # Apply max_actions budget if specified
        if self.cfg.max_actions:
            actions = actions[: self.cfg.max_actions]

        return actions

    def _calculate_priority(
        self, plan: EditPlan, cost_ranks: dict[str, int]
    ) -> tuple[float, str]:
        """
        Calculate priority for a plan with rationale.

        Priority formula:
            priority = 100*R★ + 20*cohesion - cost_rank - revert_penalty + context_boost

        Returns:
            Tuple of (priority, rationale_string)
        """
        # Base priority from R★ score
        rstar = plan.estimated_risk
        base_priority = 100 * rstar

        # Get rule IDs for this plan
        rule_ids = get_rule_ids_from_plan(plan)

        # Cost penalty (average rank of rules in plan)
        cost_penalty = 0.0
        if rule_ids and cost_ranks:
            cost_penalty = sum(cost_ranks.get(rid, 0) for rid in rule_ids) / len(rule_ids)

        # Revert penalty (check if context was reverted recently)
        revert_penalty = 0.0
        ctx_key = context_key(plan)
        if self.learning and self.learning.should_skip_context(ctx_key, threshold=0.5):
            revert_penalty = 20.0  # Significant penalty for previously reverted contexts

        # Cohesion bonus (files with multiple issues get grouped)
        cohesion_bonus = 0.0
        if plan.findings:
            # Count unique files in findings
            unique_files = set(f.file for f in plan.findings)
            if len(unique_files) == 1 and len(plan.findings) > 1:
                # Multiple issues in same file = cohesive
                cohesion_bonus = 20.0

        # Context boost (using RepoMap and DepGraph)
        context_boost = 0.0
        if self.context_ranker and self.repo_map and hasattr(plan, "edits") and plan.edits:
            # Get files affected by this plan
            affected_files = list(set(edit.file_path for edit in plan.edits))

            # Score each file
            total_score = 0.0
            for file_path in affected_files:
                # Try to get relative path
                try:
                    rel_path = str(Path(file_path).relative_to(self.cfg.target))
                except ValueError:
                    rel_path = str(file_path)

                # Get file symbols and calculate density/recency
                file_symbols = self.repo_map.get_file_symbols(rel_path)
                if file_symbols:
                    # Use ranker's scoring components
                    file_score = self.context_ranker._score_file(
                        rel_path, query=None, recency_weight=0.3, density_weight=0.5, relevance_weight=0.0
                    )
                    if file_score:
                        total_score += file_score.score

            # Average boost across files
            if affected_files:
                context_boost = (total_score / len(affected_files)) * 5.0  # Scale to ~5 points max

        # Learning: Success rate bonus (prefer high-success rules)
        success_rate_bonus = 0.0
        if self.learning and rule_ids:
            success_rates = []
            for rule_id in rule_ids:
                if rule_id in self.learning.data.rules:
                    stats = self.learning.data.rules[rule_id]
                    if stats.sample_size() >= 5:  # Only consider rules with enough samples
                        success_rates.append(stats.success_rate())

            if success_rates:
                avg_success_rate = sum(success_rates) / len(success_rates)
                success_rate_bonus = avg_success_rate * 10.0  # Scale to ~10 points max

        # Final priority
        priority = (
            base_priority + cohesion_bonus - cost_penalty - revert_penalty + context_boost + success_rate_bonus
        )

        # Build rationale
        rationale_parts = []

        if rstar >= 0.8:
            rationale_parts.append(f"high-risk (R★={rstar:.2f})")
        elif rstar >= 0.6:
            rationale_parts.append(f"medium-risk (R★={rstar:.2f})")

        if cohesion_bonus > 0:
            rationale_parts.append("cohesive changes")

        if success_rate_bonus > 5:
            rationale_parts.append("high success rate")

        if revert_penalty > 0:
            rationale_parts.append("recently reverted")

        if context_boost > 2:
            rationale_parts.append("important context")

        if not rationale_parts:
            rationale_parts.append("standard priority")

        rationale = "; ".join(rationale_parts)

        return (priority, rationale)


def plan_actions(cfg: PlannerConfig, plans: list[EditPlan]) -> list[Action]:
    """
    Convenience function to plan actions from edit plans.

    Args:
        cfg: Planner configuration
        plans: List of EditPlan objects

    Returns:
        Ordered list of Action objects with priorities and rationales
    """
    planner = Planner(cfg)
    return planner.plan_actions(plans)
