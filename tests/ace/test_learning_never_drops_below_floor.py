"""Test that thresholds never drop below floor values."""

import tempfile
from pathlib import Path

from ace.learn import FLOOR_MIN_AUTO, CEIL_MIN_AUTO, LearningEngine


def test_threshold_never_below_floor():
    """Test that auto threshold never goes below floor (0.60)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        # Simulate extremely high apply rate (100%)
        rule_id = "PY-S101-UNSAFE-HTTP"
        for _ in range(20):
            learning.record_outcome(rule_id, "applied")

        tuned_auto, _ = learning.tuned_thresholds(rule_id)

        # Should not go below floor
        assert tuned_auto >= FLOOR_MIN_AUTO


def test_threshold_never_above_ceiling():
    """Test that auto threshold never goes above ceiling (0.85)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        # Simulate extremely high revert rate (100%)
        rule_id = "PY-E201-BROAD-EXCEPT"
        for _ in range(20):
            learning.record_outcome(rule_id, "reverted")

        tuned_auto, _ = learning.tuned_thresholds(rule_id)

        # Should not go above ceiling
        assert tuned_auto <= CEIL_MIN_AUTO


def test_multiple_adjustments_respect_floor():
    """Test that multiple downward adjustments still respect floor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        rule_id = "PY-I101-IMPORT-SORT"

        # Record many successful applications (should drive threshold down)
        for _ in range(50):
            learning.record_outcome(rule_id, "applied")

        tuned_auto, _ = learning.tuned_thresholds(rule_id)

        # Even with 100% success rate, should not go below floor
        assert tuned_auto >= FLOOR_MIN_AUTO
        # Should be at or near floor due to many applications
        assert tuned_auto <= FLOOR_MIN_AUTO + 0.10  # Within 0.10 of floor


def test_multiple_adjustments_respect_ceiling():
    """Test that multiple upward adjustments still respect ceiling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        rule_id = "PY-S201-SUBPROCESS-CHECK"

        # Record many reverts (should drive threshold up)
        for _ in range(50):
            learning.record_outcome(rule_id, "reverted")

        tuned_auto, _ = learning.tuned_thresholds(rule_id)

        # Even with 100% revert rate, should not go above ceiling
        assert tuned_auto <= CEIL_MIN_AUTO
        # Should be at or near ceiling due to many reverts
        assert tuned_auto >= CEIL_MIN_AUTO - 0.10  # Within 0.10 of ceiling


def test_suggest_threshold_unchanged():
    """Test that suggest threshold remains unchanged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        rule_id = "PY-E201-BROAD-EXCEPT"

        # Record mix of outcomes
        for _ in range(10):
            learning.record_outcome(rule_id, "applied")
        for _ in range(5):
            learning.record_outcome(rule_id, "reverted")

        _, tuned_suggest = learning.tuned_thresholds(rule_id)

        # Suggest threshold should remain at default (0.50)
        assert tuned_suggest == 0.50


def test_different_rules_have_independent_thresholds():
    """Test that different rules have independent threshold adjustments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        # Rule 1: High revert rate
        rule1 = "PY-E201-BROAD-EXCEPT"
        for _ in range(1):
            learning.record_outcome(rule1, "applied")
        for _ in range(5):
            learning.record_outcome(rule1, "reverted")

        # Rule 2: High apply rate
        rule2 = "PY-S101-UNSAFE-HTTP"
        for _ in range(10):
            learning.record_outcome(rule2, "applied")
        for _ in range(1):
            learning.record_outcome(rule2, "reverted")

        tuned_auto_1, _ = learning.tuned_thresholds(rule1)
        tuned_auto_2, _ = learning.tuned_thresholds(rule2)

        # Rule 1 should have increased threshold
        assert tuned_auto_1 > 0.70
        # Rule 2 should have decreased threshold
        assert tuned_auto_2 < 0.70
        # They should be different
        assert tuned_auto_1 != tuned_auto_2
