"""Test learning threshold adjustments based on outcomes."""

import tempfile
from pathlib import Path

from ace.learn import (
    DEFAULT_MIN_AUTO,
    DEFAULT_MIN_SUGGEST,
    FLOOR_MIN_AUTO,
    CEIL_MIN_AUTO,
    LearningEngine,
)


def test_threshold_increases_on_high_revert_rate():
    """Test that threshold increases when revert rate is high."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        # Simulate high revert rate: 2 applied, 4 reverted (66% revert rate) - need at least 5 actions
        rule_id = "PY-E201-BROAD-EXCEPT"
        learning.record_outcome(rule_id, "applied")
        learning.record_outcome(rule_id, "applied")
        learning.record_outcome(rule_id, "reverted")
        learning.record_outcome(rule_id, "reverted")
        learning.record_outcome(rule_id, "reverted")
        learning.record_outcome(rule_id, "reverted")

        # Get tuned thresholds
        tuned_auto, tuned_suggest = learning.tuned_thresholds(rule_id)

        # Should have increased auto threshold due to high revert rate (>25%)
        assert tuned_auto > DEFAULT_MIN_AUTO
        # Suggest threshold should remain unchanged
        assert tuned_suggest == DEFAULT_MIN_SUGGEST


def test_threshold_decreases_on_high_apply_rate():
    """Test that threshold decreases when apply rate is high."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        # Simulate high apply rate: 8 applied, 1 reverted (88.9% apply rate)
        rule_id = "PY-S101-UNSAFE-HTTP"
        for _ in range(8):
            learning.record_outcome(rule_id, "applied")
        learning.record_outcome(rule_id, "reverted")

        # Get tuned thresholds
        tuned_auto, tuned_suggest = learning.tuned_thresholds(rule_id)

        # Should have decreased auto threshold due to high apply rate (>80%)
        assert tuned_auto < DEFAULT_MIN_AUTO
        # Suggest threshold should remain unchanged
        assert tuned_suggest == DEFAULT_MIN_SUGGEST


def test_threshold_stable_with_moderate_rates():
    """Test that threshold remains stable with moderate rates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        # Simulate moderate rates: 3 applied, 2 reverted (40% revert rate, 60% apply rate)
        # Revert rate is >25% but apply rate is <80%, so both conditions can't be true
        # Actually, revert rate >25% will trigger increase. Let's use lower revert rate.
        # Use: 7 applied, 1 reverted (12.5% revert rate, 87.5% apply rate)
        # But 87.5% > 80% will trigger decrease. Need middle ground.
        # Let's use: 3 applied, 1 reverted (25% revert rate, 75% apply rate)
        # This is exactly at revert threshold, so won't trigger (need >25%)
        rule_id = "PY-I101-IMPORT-SORT"
        learning.record_outcome(rule_id, "applied")
        learning.record_outcome(rule_id, "applied")
        learning.record_outcome(rule_id, "applied")
        learning.record_outcome(rule_id, "reverted")

        # Get tuned thresholds
        tuned_auto, tuned_suggest = learning.tuned_thresholds(rule_id)

        # Should remain at defaults (25% revert = exactly at threshold, won't trigger)
        assert tuned_auto == DEFAULT_MIN_AUTO
        assert tuned_suggest == DEFAULT_MIN_SUGGEST


def test_threshold_requires_minimum_data():
    """Test that threshold adjustment requires minimum data points."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        # Simulate only 3 outcomes (below minimum of 5)
        rule_id = "PY-S201-SUBPROCESS-CHECK"
        learning.record_outcome(rule_id, "reverted")
        learning.record_outcome(rule_id, "reverted")
        learning.record_outcome(rule_id, "applied")

        # Get tuned thresholds
        tuned_auto, tuned_suggest = learning.tuned_thresholds(rule_id)

        # Should remain at defaults (not enough data)
        assert tuned_auto == DEFAULT_MIN_AUTO
        assert tuned_suggest == DEFAULT_MIN_SUGGEST


def test_multiple_threshold_adjustments():
    """Test threshold adjustments over multiple learning cycles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        learning = LearningEngine(learn_path=learn_path)

        rule_id = "PY-E201-BROAD-EXCEPT"

        # First cycle: High revert rate
        for _ in range(2):
            learning.record_outcome(rule_id, "applied")
        for _ in range(4):
            learning.record_outcome(rule_id, "reverted")

        tuned_auto_1, _ = learning.tuned_thresholds(rule_id)
        assert tuned_auto_1 > DEFAULT_MIN_AUTO

        # Second cycle: Add more successful applications
        for _ in range(10):
            learning.record_outcome(rule_id, "applied")

        tuned_auto_2, _ = learning.tuned_thresholds(rule_id)
        # Should now decrease since apply rate is high
        assert tuned_auto_2 < tuned_auto_1
