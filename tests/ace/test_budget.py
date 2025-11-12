"""Tests for budget orchestrator."""

from ace.budget import (
    BudgetConstraints,
    apply_budget,
    compute_plan_rstar,
    count_lines_in_plan,
)
from ace.skills.python import Edit, EditPlan
from ace.uir import Severity, UnifiedIssue


def test_compute_plan_rstar_high_severity():
    """Test R★ computation for high severity findings."""
    finding = UnifiedIssue(
        file="test.py",
        line=10,
        rule="PY-S101",
        severity=Severity.CRITICAL,
        message="Critical issue"
    )
    edit = Edit(
        file="test.py",
        start_line=10,
        end_line=10,
        op="replace",
        payload="fixed"
    )
    plan = EditPlan(
        id="p1",
        findings=[finding],
        edits=[edit],
        invariants=[],
        estimated_risk=0.3
    )

    rstar = compute_plan_rstar(plan)

    # Critical severity (1.0) + low complexity (0.1) should give high R★
    assert 0.5 < rstar <= 1.0


def test_compute_plan_rstar_low_severity():
    """Test R★ computation for low severity findings."""
    finding = UnifiedIssue(
        file="test.py",
        line=10,
        rule="PY-S310",
        severity=Severity.INFO,
        message="Trailing whitespace"
    )
    edit = Edit(
        file="test.py",
        start_line=10,
        end_line=10,
        op="replace",
        payload="fixed"
    )
    plan = EditPlan(
        id="p1",
        findings=[finding],
        edits=[edit],
        invariants=[],
        estimated_risk=0.1
    )

    rstar = compute_plan_rstar(plan)

    # Info severity (0.1) + low complexity (0.1) should give low R★
    assert 0.0 <= rstar < 0.5


def test_count_lines_in_plan_replace():
    """Test counting lines for replace operations."""
    edits = [
        Edit(
            file="test.py",
            start_line=1,
            end_line=5,
            op="replace",
            payload="new content"
        )
    ]
    plan = EditPlan(
        id="p1",
        findings=[],
        edits=edits,
        invariants=[],
        estimated_risk=0.1
    )

    lines = count_lines_in_plan(plan)

    # Lines 1-5 inclusive = 5 lines
    assert lines == 5


def test_count_lines_in_plan_insert():
    """Test counting lines for insert operations."""
    edits = [
        Edit(
            file="test.py",
            start_line=10,
            end_line=10,
            op="insert",
            payload="line1\nline2\nline3"
        )
    ]
    plan = EditPlan(
        id="p1",
        findings=[],
        edits=edits,
        invariants=[],
        estimated_risk=0.1
    )

    lines = count_lines_in_plan(plan)

    # 2 newlines + 1 = 3 lines
    assert lines == 3


def test_count_lines_in_plan_delete():
    """Test counting lines for delete operations."""
    edits = [
        Edit(
            file="test.py",
            start_line=5,
            end_line=10,
            op="delete",
            payload=""
        )
    ]
    plan = EditPlan(
        id="p1",
        findings=[],
        edits=edits,
        invariants=[],
        estimated_risk=0.1
    )

    lines = count_lines_in_plan(plan)

    # Lines 5-10 inclusive = 6 lines
    assert lines == 6


def test_apply_budget_max_files():
    """Test budget with max_files constraint."""
    # Create 3 plans for different files
    plans = [
        EditPlan(
            id="p1",
            findings=[
                UnifiedIssue(
                    file="a.py",
                    line=1,
                    rule="PY-S101",
                    severity=Severity.HIGH,
                    message="test"
                )
            ],
            edits=[
                Edit(file="a.py", start_line=1, end_line=1, op="replace", payload="x")
            ],
            invariants=[],
            estimated_risk=0.5
        ),
        EditPlan(
            id="p2",
            findings=[
                UnifiedIssue(
                    file="b.py",
                    line=1,
                    rule="PY-S101",
                    severity=Severity.MEDIUM,
                    message="test"
                )
            ],
            edits=[
                Edit(file="b.py", start_line=1, end_line=1, op="replace", payload="y")
            ],
            invariants=[],
            estimated_risk=0.3
        ),
        EditPlan(
            id="p3",
            findings=[
                UnifiedIssue(
                    file="c.py",
                    line=1,
                    rule="PY-S101",
                    severity=Severity.LOW,
                    message="test"
                )
            ],
            edits=[
                Edit(file="c.py", start_line=1, end_line=1, op="replace", payload="z")
            ],
            invariants=[],
            estimated_risk=0.1
        ),
    ]

    constraints = BudgetConstraints(max_files=2)
    included, summary = apply_budget(plans, constraints)

    # Should include only 2 files (highest R★ plans)
    assert len(included) <= 2
    assert summary.included_count <= 2
    assert summary.excluded_count >= 1


def test_apply_budget_max_lines():
    """Test budget with max_lines constraint."""
    # Create plans with different line counts
    plans = [
        EditPlan(
            id="p1",
            findings=[
                UnifiedIssue(
                    file="test.py",
                    line=1,
                    rule="PY-S101",
                    severity=Severity.HIGH,
                    message="test"
                )
            ],
            edits=[
                Edit(
                    file="test.py",
                    start_line=1,
                    end_line=10,  # 10 lines
                    op="replace",
                    payload="x"
                )
            ],
            invariants=[],
            estimated_risk=0.5
        ),
        EditPlan(
            id="p2",
            findings=[
                UnifiedIssue(
                    file="test.py",
                    line=20,
                    rule="PY-S101",
                    severity=Severity.MEDIUM,
                    message="test"
                )
            ],
            edits=[
                Edit(
                    file="test.py",
                    start_line=20,
                    end_line=25,  # 6 lines
                    op="replace",
                    payload="y"
                )
            ],
            invariants=[],
            estimated_risk=0.3
        ),
    ]

    constraints = BudgetConstraints(max_lines=12)
    included, summary = apply_budget(plans, constraints)

    # Should include only first plan (10 lines < 12)
    # Second plan would push total to 16 lines > 12
    assert summary.total_lines_modified <= 12


def test_apply_budget_priority_ordering():
    """Test that plans are ordered by R★ descending."""
    plans = [
        EditPlan(
            id="p1",
            findings=[
                UnifiedIssue(
                    file="a.py",
                    line=1,
                    rule="PY-S101",
                    severity=Severity.LOW,  # Low severity
                    message="test"
                )
            ],
            edits=[
                Edit(file="a.py", start_line=1, end_line=1, op="replace", payload="x")
            ],
            invariants=[],
            estimated_risk=0.1
        ),
        EditPlan(
            id="p2",
            findings=[
                UnifiedIssue(
                    file="b.py",
                    line=1,
                    rule="PY-S101",
                    severity=Severity.CRITICAL,  # High severity
                    message="test"
                )
            ],
            edits=[
                Edit(file="b.py", start_line=1, end_line=1, op="replace", payload="y")
            ],
            invariants=[],
            estimated_risk=0.9
        ),
    ]

    constraints = BudgetConstraints(max_files=1)
    included, summary = apply_budget(plans, constraints)

    # Should include p2 (higher R★) over p1
    assert len(included) == 1
    assert included[0].id == "p2"


def test_apply_budget_no_constraints():
    """Test budget with no constraints includes all plans."""
    plans = [
        EditPlan(
            id="p1",
            findings=[],
            edits=[
                Edit(file="test.py", start_line=1, end_line=1, op="replace", payload="x")
            ],
            invariants=[],
            estimated_risk=0.1
        )
    ]

    constraints = BudgetConstraints()
    included, summary = apply_budget(plans, constraints)

    # Should include all plans
    assert len(included) == len(plans)
    assert summary.excluded_count == 0


def test_apply_budget_empty_plans():
    """Test budget with empty plan list."""
    plans = []

    constraints = BudgetConstraints(max_files=10)
    included, summary = apply_budget(plans, constraints)

    assert len(included) == 0
    assert summary.included_count == 0
    assert summary.excluded_count == 0
