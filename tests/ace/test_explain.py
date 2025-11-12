"""Tests for explain module."""

import pytest

from ace.explain import explain_pack, explain_plan, get_explain_summary
from ace.packs import Pack, PackRecipe
from ace.skills.python import Edit, EditPlan
from ace.uir import create_uir


class TestExplainPlan:
    """Tests for plan explanation."""

    def test_explain_simple_plan(self):
        """Test explanation for simple plan."""
        finding = create_uir(
            "test.py", 10, "PY-S101-UNSAFE-HTTP", "high",
            "No timeout", "", "requests.get(url)"
        )
        edit = Edit("test.py", 10, 10, "replace", "requests.get(url, timeout=10)")
        plan = EditPlan("plan-1", [finding], [edit], [], 0.8)

        explanation = explain_plan(plan)

        # Check key sections are present
        assert "Plan ID: plan-1" in explanation
        assert "PY-S101-UNSAFE-HTTP" in explanation
        assert "test.py:10" in explanation
        assert "Risk Assessment" in explanation
        assert "R* Calculation" in explanation

    def test_explain_plan_with_pack(self):
        """Test explanation for plan with pack info."""
        recipe = PackRecipe("PY_HTTP_SAFETY", ["RULE-1"], "file", "HTTP safety")
        findings = [
            create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snip"),
        ]
        pack = Pack("pack-1", recipe, "test.py", findings, 0.9)

        plan = EditPlan("plan-1", findings, [], [], 0.8)

        explanation = explain_plan(plan, pack=pack)

        assert "Pack Information" in explanation
        assert "pack-1" in explanation
        assert "PY_HTTP_SAFETY" in explanation
        assert "Cohesion: 0.900" in explanation

    def test_explain_plan_multiple_findings(self):
        """Test explanation with multiple findings."""
        findings = [
            create_uir("test.py", 10, "RULE-1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "RULE-2", "medium", "msg2", "", "snip2"),
            create_uir("test.py", 30, "RULE-3", "low", "msg3", "", "snip3"),
        ]
        plan = EditPlan("plan-1", findings, [], [], 0.6)

        explanation = explain_plan(plan)

        assert "Total: 3" in explanation
        assert "1. test.py:10" in explanation
        assert "2. test.py:20" in explanation
        assert "3. test.py:30" in explanation

    def test_explain_plan_with_edits(self):
        """Test explanation shows edit details."""
        finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snip")
        edits = [
            Edit("test.py", 10, 15, "replace", "new code here"),
            Edit("test.py", 20, 20, "insert", "inserted code"),
        ]
        plan = EditPlan("plan-1", [finding], edits, [], 0.7)

        explanation = explain_plan(plan)

        assert "## Edits" in explanation
        assert "Total: 2" in explanation
        assert "Lines: 10-15" in explanation
        assert "Operation: replace" in explanation
        assert "Lines: 20-20" in explanation
        assert "Operation: insert" in explanation

    def test_explain_plan_with_invariants(self):
        """Test explanation includes invariants."""
        finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snip")
        plan = EditPlan(
            "plan-1",
            [finding],
            [],
            ["syntax_valid", "imports_preserved"],
            0.5
        )

        explanation = explain_plan(plan)

        assert "## Invariants" in explanation
        assert "syntax_valid" in explanation
        assert "imports_preserved" in explanation

    def test_explain_plan_decision(self):
        """Test explanation includes decision."""
        # High R* -> AUTO
        finding = create_uir("test.py", 10, "RULE-1", "critical", "msg", "", "snip")
        plan = EditPlan("plan-1", [finding], [], [], 0.9)

        explanation = explain_plan(plan)

        assert "Decision: AUTO" in explanation

    def test_explain_plan_with_policy_config(self):
        """Test explanation uses policy config."""
        finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snip")
        plan = EditPlan("plan-1", [finding], [], [], 0.6)

        policy_config = {
            "alpha": 0.8,
            "beta": 0.2,
            "auto_threshold": 0.9,
            "suggest_threshold": 0.6,
        }

        explanation = explain_plan(plan, policy_config=policy_config)

        assert "R* = 0.8" in explanation
        assert "0.2" in explanation


class TestExplainPack:
    """Tests for pack explanation."""

    def test_explain_simple_pack(self):
        """Test explanation for simple pack."""
        recipe = PackRecipe("PY_HTTP_SAFETY", ["RULE-1", "RULE-2"], "file", "HTTP safety fixes")
        findings = [
            create_uir("test.py", 10, "RULE-1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "RULE-2", "medium", "msg2", "", "snip2"),
        ]
        pack = Pack("pack-123", recipe, "test.py", findings, 0.9)

        explanation = explain_pack(pack)

        assert "Pack: pack-123" in explanation
        assert "PY_HTTP_SAFETY" in explanation
        assert "HTTP safety fixes" in explanation
        assert "Cohesion: 0.900" in explanation

    def test_explain_pack_recipe(self):
        """Test explanation includes recipe details."""
        recipe = PackRecipe("TEST_PACK", ["R1", "R2", "R3"], "function", "Test pack")
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg", "", "snip"),
        ]
        pack = Pack("pack-1", recipe, "test.py::func", findings, 0.5)

        explanation = explain_pack(pack)

        assert "## Recipe" in explanation
        assert "ID: TEST_PACK" in explanation
        assert "Context Level: function" in explanation
        assert "Rules: R1, R2, R3" in explanation

    def test_explain_pack_findings(self):
        """Test explanation includes finding details."""
        recipe = PackRecipe("TEST", ["R1"], "file", "Test")
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "R1", "high", "msg2", "", "snip2"),
        ]
        pack = Pack("pack-1", recipe, "test.py", findings, 1.0)

        explanation = explain_pack(pack)

        assert "Total: 2" in explanation
        assert "R1: 2 finding(s)" in explanation
        assert "1. test.py:10" in explanation
        assert "2. test.py:20" in explanation

    def test_explain_pack_multiple_rules(self):
        """Test explanation with multiple rules."""
        recipe = PackRecipe("TEST", ["R1", "R2"], "file", "Test")
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "R1", "high", "msg2", "", "snip2"),
            create_uir("test.py", 30, "R2", "medium", "msg3", "", "snip3"),
        ]
        pack = Pack("pack-1", recipe, "test.py", findings, 0.8)

        explanation = explain_pack(pack)

        assert "R1: 2 finding(s)" in explanation
        assert "R2: 1 finding(s)" in explanation


class TestGetExplainSummary:
    """Tests for explain summary."""

    def test_summary_empty(self):
        """Test summary with no plans or packs."""
        summary = get_explain_summary([], [])

        assert summary["total_plans"] == 0
        assert summary["pack_plans"] == 0
        assert summary["individual_plans"] == 0
        assert summary["total_packs"] == 0

    def test_summary_individual_plans(self):
        """Test summary with individual plans only."""
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "R2", "high", "msg2", "", "snip2"),
        ]
        plans = [
            EditPlan("p1", [findings[0]], [], [], 0.5),
            EditPlan("p2", [findings[1]], [], [], 0.5),
        ]

        summary = get_explain_summary(plans, [])

        assert summary["total_plans"] == 2
        assert summary["individual_plans"] == 2
        assert summary["pack_plans"] == 0

    def test_summary_with_packs(self):
        """Test summary with packs."""
        recipe = PackRecipe("TEST", ["R1", "R2"], "file", "Test")
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "R2", "high", "msg2", "", "snip2"),
        ]
        pack = Pack("pack-1", recipe, "test.py", findings, 0.9)

        # Pack plan combines both findings
        pack_plan = EditPlan("pack-plan", findings, [], [], 0.8)

        summary = get_explain_summary([pack_plan], [pack])

        assert summary["total_plans"] == 1
        assert summary["total_packs"] == 1


class TestExplainOutputFormat:
    """Tests for explanation output formatting."""

    def test_explanation_is_readable(self):
        """Test that explanation is human-readable."""
        finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snip")
        plan = EditPlan("plan-1", [finding], [], [], 0.7)

        explanation = explain_plan(plan)

        # Should be multi-line
        lines = explanation.split("\n")
        assert len(lines) > 10

        # Should have clear sections
        assert any("==" in line for line in lines)  # Section separators
        assert any("##" in line for line in lines)  # Headers

    def test_explanation_includes_context(self):
        """Test that explanation provides enough context."""
        finding = create_uir(
            "src/api/handlers.py", 42, "PY-S101-UNSAFE-HTTP",
            "high", "requests.get without timeout", "Add timeout=10",
            "response = requests.get(url)"
        )
        plan = EditPlan("plan-1", [finding], [], [], 0.8)

        explanation = explain_plan(plan)

        # File, line, rule
        assert "src/api/handlers.py" in explanation
        assert "42" in explanation
        assert "PY-S101-UNSAFE-HTTP" in explanation

        # Severity, message
        assert "high" in explanation
        assert "timeout" in explanation

        # Risk and decision
        assert "Risk Assessment" in explanation
        assert "Decision:" in explanation

    def test_pack_explanation_shows_cohesion(self):
        """Test that pack explanation emphasizes cohesion."""
        recipe = PackRecipe("PY_HTTP_SAFETY", ["R1", "R2"], "file", "HTTP safety")
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "R2", "high", "msg2", "", "snip2"),
        ]
        pack = Pack("pack-1", recipe, "test.py", findings, 1.0)

        plan = EditPlan("plan-1", findings, [], [], 0.8)
        explanation = explain_plan(plan, pack=pack)

        # Cohesion boost should be visible
        assert "cohesion" in explanation.lower()
        assert "1.000" in explanation  # Perfect cohesion

    def test_long_content_truncated(self):
        """Test that long content is truncated."""
        # Very long snippet
        long_snippet = "x" * 200
        finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", long_snippet)
        plan = EditPlan("plan-1", [finding], [], [], 0.5)

        explanation = explain_plan(plan)

        # Snippet should be truncated with "..."
        assert "..." in explanation
        # But not include full 200 chars
        assert "x" * 150 not in explanation
