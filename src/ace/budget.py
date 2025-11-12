"""
Change budget orchestrator for limiting scope of refactoring operations.

Provides guardrails on the number of files and lines modified in a single run,
with priority-based ordering to maximize value within budget constraints.
"""

from dataclasses import dataclass
from pathlib import Path

from ace.policy import rstar
from ace.skills.python import EditPlan
from ace.uir import Severity, UnifiedIssue


# Severity to numeric mapping (0.0 to 1.0)
SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.75,
    Severity.MEDIUM: 0.5,
    Severity.LOW: 0.25,
    Severity.INFO: 0.1,
}


@dataclass
class BudgetConstraints:
    """Budget constraints for refactoring operations."""
    max_files: int | None = None
    max_lines: int | None = None


@dataclass
class BudgetSummary:
    """Summary of budget usage and skipped items."""
    included_count: int
    excluded_count: int
    included_files: set[str]
    excluded_files: set[str]
    total_lines_modified: int
    skipped_lines: int

    def format_summary(self) -> str:
        """Format budget summary for display."""
        lines = [
            f"Budget Summary:",
            f"  Included: {self.included_count} plans ({len(self.included_files)} files, {self.total_lines_modified} lines)",
        ]
        if self.excluded_count > 0:
            lines.append(
                f"  Excluded: {self.excluded_count} plans ({len(self.excluded_files)} files, {self.skipped_lines} lines) - budget limit reached"
            )
        return "\n".join(lines)


def compute_plan_rstar(plan: EditPlan) -> float:
    """
    Compute R★ score for an EditPlan based on its findings.

    Uses maximum severity from all findings and a complexity estimate
    based on the number of edits.

    Args:
        plan: EditPlan to score

    Returns:
        R★ score (0.0 to 1.0)

    Examples:
        >>> from ace.uir import UnifiedIssue, Severity
        >>> from ace.skills.python import Edit, EditPlan
        >>> finding = UnifiedIssue(
        ...     file="test.py", line=10, rule="PY-S101",
        ...     severity=Severity.high, message="test"
        ... )
        >>> edit = Edit(file="test.py", start_line=10, end_line=10, op="replace", payload="fixed")
        >>> plan = EditPlan(id="p1", findings=[finding], edits=[edit], invariants=[], estimated_risk=0.3)
        >>> score = compute_plan_rstar(plan)
        >>> 0.5 < score < 1.0  # Should be high due to high severity
        True
    """
    if not plan.findings:
        return 0.0

    # Get maximum severity from findings
    max_severity = max(
        SEVERITY_WEIGHTS.get(f.severity, 0.0) for f in plan.findings
    )

    # Estimate complexity based on number of edits and lines affected
    # Normalize: 1 edit = 0.1 complexity, 10+ edits = 1.0 complexity
    complexity = min(1.0, len(plan.edits) / 10.0)

    # Use default R★ weights (α=0.6, β=0.4)
    return rstar(max_severity, complexity)


def count_lines_in_plan(plan: EditPlan) -> int:
    """
    Count total lines affected by an EditPlan.

    Args:
        plan: EditPlan to count

    Returns:
        Total number of lines affected (insertions + modifications + deletions)

    Examples:
        >>> from ace.skills.python import Edit, EditPlan
        >>> edits = [
        ...     Edit(file="test.py", start_line=1, end_line=5, op="replace", payload="new"),
        ...     Edit(file="test.py", start_line=10, end_line=10, op="insert", payload="inserted"),
        ... ]
        >>> plan = EditPlan(id="p1", findings=[], edits=edits, invariants=[], estimated_risk=0.1)
        >>> count_lines_in_plan(plan)
        6
    """
    total = 0
    for edit in plan.edits:
        if edit.op in {"replace", "delete"}:
            # Count lines being replaced or deleted
            total += edit.end_line - edit.start_line + 1
        elif edit.op == "insert":
            # Count inserted lines (count newlines in payload)
            total += edit.payload.count("\n") + 1

    return total


def apply_budget(
    plans: list[EditPlan],
    constraints: BudgetConstraints
) -> tuple[list[EditPlan], BudgetSummary]:
    """
    Apply budget constraints to list of EditPlans.

    Orders plans by (R★ desc, file path asc) and includes plans until
    budget limits are reached. Returns included plans and summary.

    Args:
        plans: List of EditPlans to prioritize
        constraints: Budget constraints (max_files, max_lines)

    Returns:
        Tuple of (included_plans, budget_summary)

    Examples:
        >>> from ace.uir import UnifiedIssue, Severity
        >>> from ace.skills.python import Edit, EditPlan
        >>> plans = [
        ...     EditPlan(
        ...         id="p1",
        ...         findings=[UnifiedIssue(file="a.py", line=1, rule="R1", severity=Severity.high, message="m")],
        ...         edits=[Edit(file="a.py", start_line=1, end_line=1, op="replace", payload="x")],
        ...         invariants=[],
        ...         estimated_risk=0.5
        ...     ),
        ...     EditPlan(
        ...         id="p2",
        ...         findings=[UnifiedIssue(file="b.py", line=1, rule="R1", severity=Severity.low, message="m")],
        ...         edits=[Edit(file="b.py", start_line=1, end_line=1, op="replace", payload="y")],
        ...         invariants=[],
        ...         estimated_risk=0.1
        ...     ),
        ... ]
        >>> included, summary = apply_budget(plans, BudgetConstraints(max_files=1))
        >>> len(included)
        1
        >>> summary.excluded_count
        1
    """
    if not plans:
        return [], BudgetSummary(
            included_count=0,
            excluded_count=0,
            included_files=set(),
            excluded_files=set(),
            total_lines_modified=0,
            skipped_lines=0
        )

    # Compute R★ for each plan and attach to metadata
    scored_plans = []
    for plan in plans:
        rstar_score = compute_plan_rstar(plan)
        # Extract file path from first finding or first edit
        file_path = ""
        if plan.findings:
            file_path = plan.findings[0].file
        elif plan.edits:
            file_path = plan.edits[0].file

        scored_plans.append((rstar_score, file_path, plan))

    # Sort by (R★ desc, then path asc) for deterministic ordering
    scored_plans.sort(key=lambda x: (-x[0], x[1]))

    # Apply budget constraints
    included = []
    excluded = []
    files_seen = set()
    total_lines = 0

    for rstar_score, file_path, plan in scored_plans:
        lines_in_plan = count_lines_in_plan(plan)
        plan_files = {edit.file for edit in plan.edits}

        # Check if adding this plan would exceed budget
        would_exceed_files = (
            constraints.max_files is not None
            and len(files_seen | plan_files) > constraints.max_files
        )
        would_exceed_lines = (
            constraints.max_lines is not None
            and total_lines + lines_in_plan > constraints.max_lines
        )

        if would_exceed_files or would_exceed_lines:
            excluded.append(plan)
        else:
            included.append(plan)
            files_seen.update(plan_files)
            total_lines += lines_in_plan

    # Build summary
    excluded_files = set()
    skipped_lines = 0
    for plan in excluded:
        for edit in plan.edits:
            excluded_files.add(edit.file)
        skipped_lines += count_lines_in_plan(plan)

    summary = BudgetSummary(
        included_count=len(included),
        excluded_count=len(excluded),
        included_files=files_seen,
        excluded_files=excluded_files,
        total_lines_modified=total_lines,
        skipped_lines=skipped_lines
    )

    return included, summary


def format_excluded_summary(excluded_plans: list[EditPlan]) -> str:
    """
    Format summary of excluded plans for display.

    Args:
        excluded_plans: Plans that were excluded due to budget

    Returns:
        Formatted summary string

    Examples:
        >>> from ace.skills.python import EditPlan
        >>> plans = [
        ...     EditPlan(id="p1", findings=[], edits=[], invariants=[], estimated_risk=0.1),
        ...     EditPlan(id="p2", findings=[], edits=[], invariants=[], estimated_risk=0.2),
        ... ]
        >>> summary = format_excluded_summary(plans)
        >>> "2 plans excluded" in summary
        True
    """
    if not excluded_plans:
        return "No plans excluded."

    lines = [f"\n{len(excluded_plans)} plans excluded due to budget constraints:"]

    # Group by file
    by_file: dict[str, list[str]] = {}
    for plan in excluded_plans:
        for edit in plan.edits:
            if edit.file not in by_file:
                by_file[edit.file] = []
            by_file[edit.file].append(plan.id)

    for file_path in sorted(by_file.keys()):
        plan_ids = by_file[file_path]
        lines.append(f"  {file_path}: {len(plan_ids)} plan(s)")

    return "\n".join(lines)
