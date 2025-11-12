"""Tests for learning skiplist module."""

import tempfile
from pathlib import Path

import pytest

from ace.skiplist import (
    Skiplist,
    add_pack_to_skiplist,
    add_plan_to_skiplist,
)
from ace.skills.python import Edit, EditPlan
from ace.uir import create_uir


class TestSkiplistBasics:
    """Tests for basic skiplist operations."""

    def test_init_creates_empty_skiplist(self):
        """Test that new skiplist is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)
            assert len(skiplist.entries) == 0

    def test_add_entry(self):
        """Test adding an entry to skiplist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            key = skiplist.add(
                rule_id="RULE-1",
                content="code snippet",
                context_path="test.py",
                reason="reverted",
            )

            assert key in skiplist.entries
            assert skiplist.entries[key].rule_id == "RULE-1"
            assert skiplist.entries[key].reason == "reverted"

    def test_compute_key_deterministic(self):
        """Test that key computation is deterministic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            key1 = skiplist.compute_key("RULE-1", "snippet", "test.py")
            key2 = skiplist.compute_key("RULE-1", "snippet", "test.py")

            assert key1 == key2

    def test_compute_key_unique(self):
        """Test that different inputs produce different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            key1 = skiplist.compute_key("RULE-1", "snippet", "test.py")
            key2 = skiplist.compute_key("RULE-2", "snippet", "test.py")
            key3 = skiplist.compute_key("RULE-1", "different", "test.py")

            assert key1 != key2
            assert key1 != key3

    def test_save_and_load(self):
        """Test that skiplist persists across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"

            # Add entries
            skiplist1 = Skiplist(skiplist_path)
            skiplist1.add("RULE-1", "snippet1", "test.py", "reverted")
            skiplist1.add("RULE-2", "snippet2", "test.py", "user-skip")

            # Load in new instance
            skiplist2 = Skiplist(skiplist_path)

            assert len(skiplist2.entries) == 2


class TestSkiplistShoudSkip:
    """Tests for skip checking logic."""

    def test_should_skip_matching_entry(self):
        """Test that matching entry is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            skiplist.add("RULE-1", "snippet", "test.py")

            assert skiplist.should_skip("RULE-1", "snippet", "test.py") is True

    def test_should_not_skip_different_rule(self):
        """Test that different rule is not skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            skiplist.add("RULE-1", "snippet", "test.py")

            assert skiplist.should_skip("RULE-2", "snippet", "test.py") is False

    def test_should_not_skip_different_content(self):
        """Test that different content is not skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            skiplist.add("RULE-1", "snippet1", "test.py")

            assert skiplist.should_skip("RULE-1", "snippet2", "test.py") is False

    def test_should_skip_finding(self):
        """Test should_skip_finding with UnifiedIssue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snippet")

            # Not skipped initially
            assert skiplist.should_skip_finding(finding) is False

            # Add to skiplist
            skiplist.add("RULE-1", "snippet", "test.py")

            # Now skipped
            assert skiplist.should_skip_finding(finding) is True

    def test_should_skip_plan(self):
        """Test should_skip_plan with EditPlan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snippet")
            plan = EditPlan(
                id="plan-1",
                findings=[finding],
                edits=[Edit("test.py", 10, 10, "replace", "new code")],
                invariants=[],
                estimated_risk=0.5,
            )

            # Not skipped initially
            assert skiplist.should_skip_plan(plan) is False

            # Add to skiplist
            skiplist.add("RULE-1", "snippet", "test.py")

            # Now skipped
            assert skiplist.should_skip_plan(plan) is True


class TestSkiplistFiltering:
    """Tests for filtering findings and plans."""

    def test_filter_findings(self):
        """Test filtering findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            findings = [
                create_uir("test.py", 10, "RULE-1", "high", "msg1", "", "snip1"),
                create_uir("test.py", 20, "RULE-2", "high", "msg2", "", "snip2"),
                create_uir("test.py", 30, "RULE-3", "high", "msg3", "", "snip3"),
            ]

            # Skip RULE-2
            skiplist.add("RULE-2", "snip2", "test.py")

            kept, skipped = skiplist.filter_findings(findings)

            assert len(kept) == 2
            assert len(skipped) == 1
            assert skipped[0].rule == "RULE-2"

    def test_filter_plans(self):
        """Test filtering plans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            finding1 = create_uir("test.py", 10, "RULE-1", "high", "msg1", "", "snip1")
            finding2 = create_uir("test.py", 20, "RULE-2", "high", "msg2", "", "snip2")

            plan1 = EditPlan("p1", [finding1], [], [], 0.5)
            plan2 = EditPlan("p2", [finding2], [], [], 0.5)

            # Skip RULE-2
            skiplist.add("RULE-2", "snip2", "test.py")

            kept, skipped = skiplist.filter_plans([plan1, plan2])

            assert len(kept) == 1
            assert len(skipped) == 1
            assert skipped[0].id == "p2"


class TestSkiplistManagement:
    """Tests for skiplist management operations."""

    def test_remove_entry(self):
        """Test removing an entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            key = skiplist.add("RULE-1", "snippet", "test.py")
            assert key in skiplist.entries

            result = skiplist.remove(key)
            assert result is True
            assert key not in skiplist.entries

    def test_remove_nonexistent(self):
        """Test removing non-existent entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            result = skiplist.remove("nonexistent-key")
            assert result is False

    def test_clear(self):
        """Test clearing all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            skiplist.add("RULE-1", "snip1", "test.py")
            skiplist.add("RULE-2", "snip2", "test.py")

            count = skiplist.clear()
            assert count == 2
            assert len(skiplist.entries) == 0

    def test_get_summary(self):
        """Test summary statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            skiplist.add("RULE-1", "snip1", "test.py", "reverted")
            skiplist.add("RULE-1", "snip2", "test.py", "reverted")
            skiplist.add("RULE-2", "snip3", "test.py", "user-skip")

            summary = skiplist.get_summary()

            assert summary["total_entries"] == 3
            assert ("RULE-1", 2) in summary["rules"]
            assert ("RULE-2", 1) in summary["rules"]
            assert ("reverted", 2) in summary["reasons"]
            assert ("user-skip", 1) in summary["reasons"]


class TestAddPlanToSkiplist:
    """Tests for adding plans to skiplist."""

    def test_add_plan(self):
        """Test adding a plan to skiplist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            findings = [
                create_uir("test.py", 10, "RULE-1", "high", "msg1", "", "snip1"),
                create_uir("test.py", 20, "RULE-2", "high", "msg2", "", "snip2"),
            ]
            plan = EditPlan("plan-1", findings, [], [], 0.5)

            keys = add_plan_to_skiplist(plan, skiplist, "reverted")

            assert len(keys) == 2
            assert skiplist.should_skip_plan(plan) is True

    def test_add_empty_plan(self):
        """Test adding plan with no findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            plan = EditPlan("plan-1", [], [], [], 0.5)

            keys = add_plan_to_skiplist(plan, skiplist)

            assert len(keys) == 0


class TestAddPackToSkiplist:
    """Tests for adding packs to skiplist."""

    def test_add_pack(self):
        """Test adding a pack to skiplist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            findings = [
                create_uir("test.py", 10, "RULE-1", "high", "msg1", "", "snip1"),
                create_uir("test.py", 20, "RULE-2", "high", "msg2", "", "snip2"),
            ]

            keys = add_pack_to_skiplist("pack-123", findings, skiplist, "pack-skipped")

            assert len(keys) == 2

            # All findings should be skipped
            for finding in findings:
                assert skiplist.should_skip_finding(finding) is True

            # Reason should include pack ID
            entry = list(skiplist.entries.values())[0]
            assert "pack-123" in entry.reason


class TestSkiplistLearning:
    """Integration tests for skiplist learning scenarios."""

    def test_learn_from_revert(self):
        """Test learning from user revert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            # User applies a fix
            finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snip")
            plan = EditPlan("plan-1", [finding], [], [], 0.5)

            # User reverts it
            add_plan_to_skiplist(plan, skiplist, "reverted")

            # Next run: same finding should be skipped
            assert skiplist.should_skip_plan(plan) is True

    def test_learn_from_pack_skip(self):
        """Test learning from pack skip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            # User skips a pack
            findings = [
                create_uir("test.py", 10, "RULE-1", "high", "msg1", "", "snip1"),
                create_uir("test.py", 20, "RULE-2", "high", "msg2", "", "snip2"),
            ]
            add_pack_to_skiplist("pack-abc", findings, skiplist)

            # Next run: those findings should be skipped
            for finding in findings:
                assert skiplist.should_skip_finding(finding) is True

    def test_skiplist_reduces_noise(self):
        """Test that skiplist reduces repeat suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"
            skiplist = Skiplist(skiplist_path)

            # Initial run: 5 findings
            findings = [
                create_uir("test.py", i * 10, f"RULE-{i}", "high", f"msg{i}", "", f"snip{i}")
                for i in range(1, 6)
            ]

            # User reverts 2 of them
            plan1 = EditPlan("p1", [findings[0]], [], [], 0.5)
            plan2 = EditPlan("p2", [findings[2]], [], [], 0.5)
            add_plan_to_skiplist(plan1, skiplist, "reverted")
            add_plan_to_skiplist(plan2, skiplist, "reverted")

            # Next run: filter findings
            kept, skipped = skiplist.filter_findings(findings)

            assert len(kept) == 3  # 3 new suggestions
            assert len(skipped) == 2  # 2 previously reverted

    def test_skiplist_persists_across_runs(self):
        """Test that skiplist persists across runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skiplist_path = Path(tmpdir) / "skiplist.json"

            # Run 1: Add skip entry
            skiplist1 = Skiplist(skiplist_path)
            finding = create_uir("test.py", 10, "RULE-1", "high", "msg", "", "snip")
            plan = EditPlan("p1", [finding], [], [], 0.5)
            add_plan_to_skiplist(plan, skiplist1, "reverted")

            # Run 2: Load skiplist and check
            skiplist2 = Skiplist(skiplist_path)
            assert skiplist2.should_skip_plan(plan) is True

            # Run 3: Still persists
            skiplist3 = Skiplist(skiplist_path)
            assert skiplist3.should_skip_plan(plan) is True
