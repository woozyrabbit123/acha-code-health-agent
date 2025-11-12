"""Tests for macro-fix packs module."""

import pytest

from ace.packs import (
    Pack,
    PackRecipe,
    compute_context_id,
    compute_pack_id,
    filter_packs_by_rules,
    find_packs,
    get_pack_summary,
)
from ace.uir import create_uir


class TestContextId:
    """Tests for context ID computation."""

    def test_file_context(self):
        """Test file-level context."""
        finding = create_uir("test.py", 42, "RULE-1", "high", "message", "", "snippet")
        context_id = compute_context_id(finding, "file")
        assert context_id == "test.py"

    def test_function_context(self):
        """Test function-level context (50-line buckets)."""
        finding1 = create_uir("test.py", 25, "RULE-1", "high", "msg", "", "snip")
        finding2 = create_uir("test.py", 35, "RULE-2", "high", "msg", "", "snip")

        context1 = compute_context_id(finding1, "function")
        context2 = compute_context_id(finding2, "function")

        # Both in same 50-line bucket (0-50)
        assert context1 == context2
        assert "L0-50" in context1

    def test_class_context(self):
        """Test class-level context (100-line buckets)."""
        finding1 = create_uir("test.py", 50, "RULE-1", "high", "msg", "", "snip")
        finding2 = create_uir("test.py", 150, "RULE-2", "high", "msg", "", "snip")

        context1 = compute_context_id(finding1, "class")
        context2 = compute_context_id(finding2, "class")

        # Different 100-line buckets
        assert context1 != context2
        assert "L0-100" in context1
        assert "L100-200" in context2


class TestPackId:
    """Tests for pack ID computation."""

    def test_deterministic(self):
        """Test that pack IDs are deterministic."""
        pack_id1 = compute_pack_id("test.py::func", "PY_HTTP_SAFETY")
        pack_id2 = compute_pack_id("test.py::func", "PY_HTTP_SAFETY")
        assert pack_id1 == pack_id2

    def test_unique_per_context(self):
        """Test that different contexts have different pack IDs."""
        pack_id1 = compute_pack_id("test1.py", "PY_HTTP_SAFETY")
        pack_id2 = compute_pack_id("test2.py", "PY_HTTP_SAFETY")
        assert pack_id1 != pack_id2

    def test_unique_per_recipe(self):
        """Test that different recipes have different pack IDs."""
        pack_id1 = compute_pack_id("test.py", "PY_HTTP_SAFETY")
        pack_id2 = compute_pack_id("test.py", "PY_CODE_QUALITY")
        assert pack_id1 != pack_id2


class TestFindPacks:
    """Tests for pack finding algorithm."""

    def test_empty_findings(self):
        """Test with no findings."""
        packs = find_packs([])
        assert len(packs) == 0

    def test_single_finding(self):
        """Test with single finding (min_findings=2)."""
        findings = [
            create_uir("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg", "", "snip"),
        ]
        packs = find_packs(findings, min_findings=2)
        assert len(packs) == 0

    def test_two_related_findings(self):
        """Test with two related findings in same context."""
        findings = [
            create_uir("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg1", "", "snip1"),
            create_uir("test.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg2", "", "snip2"),
        ]
        packs = find_packs(findings, min_findings=2)

        assert len(packs) >= 1
        # Should match PY_HTTP_SAFETY pack (contains both rules)
        http_safety_pack = next((p for p in packs if p.recipe.id == "PY_HTTP_SAFETY"), None)
        assert http_safety_pack is not None
        assert len(http_safety_pack.findings) == 2

    def test_different_contexts(self):
        """Test that findings in different contexts form separate packs."""
        findings = [
            create_uir("test1.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg1", "", "snip1"),
            create_uir("test1.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg2", "", "snip2"),
            create_uir("test2.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg3", "", "snip3"),
            create_uir("test2.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg4", "", "snip4"),
        ]
        packs = find_packs(findings, min_findings=2)

        # Should find 2 packs (one per file)
        http_safety_packs = [p for p in packs if p.recipe.id == "PY_HTTP_SAFETY"]
        assert len(http_safety_packs) >= 2

    def test_cohesion_calculation(self):
        """Test that cohesion is calculated correctly."""
        # Pack recipe has 3 rules, but we only have 2
        findings = [
            create_uir("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg1", "", "snip1"),
            create_uir("test.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg2", "", "snip2"),
        ]
        packs = find_packs(findings, min_findings=2)

        http_safety_pack = next((p for p in packs if p.recipe.id == "PY_HTTP_SAFETY"), None)
        assert http_safety_pack is not None

        # Cohesion = 2 unique rules / 3 total rules in recipe = 0.666...
        assert http_safety_pack.cohesion > 0.6
        assert http_safety_pack.cohesion < 0.7

    def test_min_findings_threshold(self):
        """Test min_findings threshold."""
        findings = [
            create_uir("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg1", "", "snip1"),
            create_uir("test.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg2", "", "snip2"),
        ]

        # With min_findings=3, no pack should form
        packs = find_packs(findings, min_findings=3)
        assert len(packs) == 0

        # With min_findings=2, pack should form
        packs = find_packs(findings, min_findings=2)
        assert len(packs) >= 1

    def test_custom_recipes(self):
        """Test with custom pack recipes."""
        recipe = PackRecipe(
            id="CUSTOM_PACK",
            rules=["RULE-A", "RULE-B"],
            context="file",
            description="Custom test pack",
        )
        findings = [
            create_uir("test.py", 10, "RULE-A", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "RULE-B", "high", "msg2", "", "snip2"),
        ]

        packs = find_packs(findings, recipes=[recipe], min_findings=2)

        assert len(packs) == 1
        assert packs[0].recipe.id == "CUSTOM_PACK"
        assert len(packs[0].findings) == 2

    def test_sorting(self):
        """Test that packs are sorted by cohesion (desc) and context_id."""
        findings = [
            # Perfect cohesion pack (1 rule out of 1)
            create_uir("a.py", 10, "PY-E201-BROAD-EXCEPT", "medium", "msg1", "", "snip1"),
            create_uir("a.py", 20, "PY-E201-BROAD-EXCEPT", "medium", "msg2", "", "snip2"),
            # Partial cohesion pack (2 rules out of 3)
            create_uir("b.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg3", "", "snip3"),
            create_uir("b.py", 20, "PY-S201-SUBPROCESS-CHECK", "high", "msg4", "", "snip4"),
        ]

        packs = find_packs(findings, min_findings=2)

        # Should be sorted by cohesion (descending)
        if len(packs) >= 2:
            assert packs[0].cohesion >= packs[1].cohesion


class TestPackFiltering:
    """Tests for pack filtering."""

    def test_filter_by_rules(self):
        """Test filtering packs by enabled rules."""
        findings = [
            create_uir("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg1", "", "snip1"),
            create_uir("test.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg2", "", "snip2"),
            create_uir("test.py", 20, "PY-Q202-PRINT-IN-SRC", "low", "msg3", "", "snip3"),
            create_uir("test.py", 25, "PY-Q201-ASSERT-IN-NONTEST", "low", "msg4", "", "snip4"),
        ]

        packs = find_packs(findings, min_findings=2)

        # Filter to only security rules
        enabled_rules = ["PY-S101-UNSAFE-HTTP", "PY-S201-SUBPROCESS-CHECK"]
        filtered = filter_packs_by_rules(packs, enabled_rules)

        # All packs should only contain enabled rules
        for pack in filtered:
            for finding in pack.findings:
                assert finding.rule in enabled_rules


class TestPackSummary:
    """Tests for pack summary."""

    def test_empty_summary(self):
        """Test summary with no packs."""
        summary = get_pack_summary([])
        assert summary["pack_count"] == 0
        assert summary["total_findings"] == 0
        assert summary["avg_cohesion"] == 0.0
        assert summary["recipes_used"] == []

    def test_pack_summary(self):
        """Test summary with packs."""
        findings = [
            create_uir("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg1", "", "snip1"),
            create_uir("test.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg2", "", "snip2"),
        ]

        packs = find_packs(findings, min_findings=2)
        summary = get_pack_summary(packs)

        assert summary["pack_count"] >= 1
        assert summary["total_findings"] >= 2
        assert 0.0 <= summary["avg_cohesion"] <= 1.0
        assert len(summary["recipes_used"]) >= 1


class TestPackDataclass:
    """Tests for Pack dataclass."""

    def test_pack_to_dict(self):
        """Test Pack serialization."""
        recipe = PackRecipe("TEST", ["R1", "R2"], "file", "Test pack")
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg1", "", "snip1"),
            create_uir("test.py", 20, "R2", "high", "msg2", "", "snip2"),
        ]
        pack = Pack("pack-id", recipe, "test.py", findings, 1.0)

        pack_dict = pack.to_dict()

        assert pack_dict["id"] == "pack-id"
        assert pack_dict["recipe_id"] == "TEST"
        assert pack_dict["context_id"] == "test.py"
        assert pack_dict["cohesion"] == 1.0
        assert pack_dict["finding_count"] == 2
        assert pack_dict["rule_count"] == 2
