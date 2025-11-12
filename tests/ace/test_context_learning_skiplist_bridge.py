"""Test context-based learning and skip list integration."""

import tempfile
from pathlib import Path

from ace.learn import LearningEngine, context_key
from ace.skills.python import EditPlan
from ace.uir import create_uir


def test_context_key_generation():
    """Test that context keys are generated consistently."""
    # Create a mock plan with findings
    finding1 = create_uir(
        file="test.py",
        line=10,
        rule="PY-E201-BROAD-EXCEPT",
        severity="medium",
        message="Broad except",
        snippet="except:\n    pass",
    )

    plan = EditPlan(
        id="test-plan-1",
        findings=[finding1],
        edits=[],
        invariants=[],
        estimated_risk=0.5,
    )

    ctx_key = context_key(plan)

    # Should contain file, rule, and snippet hash
    assert "test.py" in ctx_key
    assert "PY-E201-BROAD-EXCEPT" in ctx_key
    # Should have a hash component
    assert len(ctx_key.split(":")) == 3


def test_context_key_same_for_identical_plans():
    """Test that identical plans generate the same context key."""
    finding = create_uir(
        file="test.py",
        line=10,
        rule="PY-E201-BROAD-EXCEPT",
        severity="medium",
        message="Broad except",
        snippet="except:\n    pass",
    )

    plan1 = EditPlan(
        id="plan-1",
        findings=[finding],
        edits=[],
        invariants=[],
        estimated_risk=0.5,
    )

    plan2 = EditPlan(
        id="plan-2",  # Different ID
        findings=[finding],  # Same findings
        edits=[],
        invariants=[],
        estimated_risk=0.5,
    )

    # Should generate same context key (based on content, not plan ID)
    assert context_key(plan1) == context_key(plan2)


def test_high_revert_context_triggers_skip():
    """Test that high-revert contexts trigger skip recommendation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        ctx_key = "test.py:PY-E201:abc123"

        # Simulate high revert rate for this context: 3 hits, 2 reverts (66%)
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "applied", ctx_key)
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "reverted", ctx_key)
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "reverted", ctx_key)

        # Should recommend skipping
        should_skip = learning.should_skip_context(ctx_key, threshold=0.5)
        assert should_skip


def test_low_revert_context_no_skip():
    """Test that low-revert contexts don't trigger skip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        ctx_key = "test.py:PY-S101:def456"

        # Simulate low revert rate: 5 hits, 1 revert (20%)
        for _ in range(4):
            learning.record_outcome("PY-S101-UNSAFE-HTTP", "applied", ctx_key)
        learning.record_outcome("PY-S101-UNSAFE-HTTP", "reverted", ctx_key)

        # Should not recommend skipping
        should_skip = learning.should_skip_context(ctx_key, threshold=0.5)
        assert not should_skip


def test_context_requires_minimum_hits():
    """Test that context skip requires minimum number of hits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        ctx_key = "test.py:PY-I101:ghi789"

        # Only 2 hits (below minimum of 3)
        learning.record_outcome("PY-I101-IMPORT-SORT", "reverted", ctx_key)
        learning.record_outcome("PY-I101-IMPORT-SORT", "reverted", ctx_key)

        # Should not skip (not enough data)
        should_skip = learning.should_skip_context(ctx_key, threshold=0.5)
        assert not should_skip


def test_context_revert_rate_calculation():
    """Test context revert rate calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        ctx_key = "test.py:PY-E201:test123"

        # Record: 10 hits, 3 reverts
        for _ in range(7):
            learning.record_outcome("PY-E201-BROAD-EXCEPT", "applied", ctx_key)
        for _ in range(3):
            learning.record_outcome("PY-E201-BROAD-EXCEPT", "reverted", ctx_key)

        ctx_stats = learning.data.contexts[ctx_key]
        revert_rate = ctx_stats.revert_rate()

        # Should be 30%
        assert abs(revert_rate - 0.3) < 0.01


def test_different_contexts_tracked_independently():
    """Test that different contexts are tracked independently."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        ctx1 = "file1.py:PY-E201:abc"
        ctx2 = "file2.py:PY-E201:def"

        # Context 1: High revert rate
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "applied", ctx1)
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "reverted", ctx1)
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "reverted", ctx1)

        # Context 2: Low revert rate
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "applied", ctx2)
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "applied", ctx2)
        learning.record_outcome("PY-E201-BROAD-EXCEPT", "applied", ctx2)

        # Context 1 should be skipped, context 2 should not
        assert learning.should_skip_context(ctx1, threshold=0.5)
        assert not learning.should_skip_context(ctx2, threshold=0.5)


def test_context_skip_with_custom_threshold():
    """Test context skip with custom threshold."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        ctx_key = "test.py:PY-E201:custom"

        # 5 hits, 2 reverts (40% revert rate)
        for _ in range(3):
            learning.record_outcome("PY-E201-BROAD-EXCEPT", "applied", ctx_key)
        for _ in range(2):
            learning.record_outcome("PY-E201-BROAD-EXCEPT", "reverted", ctx_key)

        # With threshold 0.5 (50%), should not skip
        assert not learning.should_skip_context(ctx_key, threshold=0.5)

        # With threshold 0.3 (30%), should skip
        assert learning.should_skip_context(ctx_key, threshold=0.3)
