"""Test that learning data persists between runs."""

import tempfile
from pathlib import Path

from ace.learn import LearningEngine


def test_learning_data_persists():
    """Test that learning data is saved and loaded correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        # First run: Record some outcomes
        learning1 = LearningEngine(learn_path=learn_path)
        learning1.record_outcome("PY-E201-BROAD-EXCEPT", "applied")
        learning1.record_outcome("PY-E201-BROAD-EXCEPT", "reverted")
        learning1.record_outcome("PY-S101-UNSAFE-HTTP", "suggested")

        # Verify file was created
        assert learn_path.exists()

        # Second run: Load the data
        learning2 = LearningEngine(learn_path=learn_path)
        learning2.load()

        # Verify data was loaded correctly
        assert "PY-E201-BROAD-EXCEPT" in learning2.data.rules
        assert "PY-S101-UNSAFE-HTTP" in learning2.data.rules

        stats1 = learning2.data.rules["PY-E201-BROAD-EXCEPT"]
        assert stats1.applied == 1
        assert stats1.reverted == 1

        stats2 = learning2.data.rules["PY-S101-UNSAFE-HTTP"]
        assert stats2.suggested == 1


def test_learning_accumulates_across_runs():
    """Test that learning data accumulates across multiple runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        # Run 1
        learning1 = LearningEngine(learn_path=learn_path)
        learning1.record_outcome("PY-E201-BROAD-EXCEPT", "applied")
        learning1.record_outcome("PY-E201-BROAD-EXCEPT", "reverted")

        # Run 2
        learning2 = LearningEngine(learn_path=learn_path)
        learning2.load()
        learning2.record_outcome("PY-E201-BROAD-EXCEPT", "applied")
        learning2.record_outcome("PY-E201-BROAD-EXCEPT", "applied")

        # Run 3: Load and check accumulated data
        learning3 = LearningEngine(learn_path=learn_path)
        learning3.load()

        stats = learning3.data.rules["PY-E201-BROAD-EXCEPT"]
        assert stats.applied == 3  # 1 + 2
        assert stats.reverted == 1


def test_context_data_persists():
    """Test that context data persists between runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        context_key = "test.py:PY-E201:abc123"

        # Run 1
        learning1 = LearningEngine(learn_path=learn_path)
        learning1.record_outcome("PY-E201-BROAD-EXCEPT", "applied", context_key)
        learning1.record_outcome("PY-E201-BROAD-EXCEPT", "reverted", context_key)

        # Run 2: Load and verify
        learning2 = LearningEngine(learn_path=learn_path)
        learning2.load()

        assert context_key in learning2.data.contexts
        ctx_stats = learning2.data.contexts[context_key]
        assert ctx_stats.hits == 2
        assert ctx_stats.reverts == 1


def test_tuning_parameters_persist():
    """Test that tuning parameters persist between runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        # Run 1: Set custom tuning parameters
        learning1 = LearningEngine(learn_path=learn_path)
        learning1.data.tuning["alpha"] = 0.8
        learning1.data.tuning["beta"] = 0.2
        learning1.save()

        # Run 2: Load and verify
        learning2 = LearningEngine(learn_path=learn_path)
        learning2.load()

        assert learning2.data.tuning["alpha"] == 0.8
        assert learning2.data.tuning["beta"] == 0.2


def test_empty_learning_file_handled():
    """Test that missing learning file is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        # Load from non-existent file
        learning = LearningEngine(learn_path=learn_path)
        learning.load()

        # Should have empty data
        assert len(learning.data.rules) == 0
        assert len(learning.data.contexts) == 0


def test_corrupted_learning_file_handled():
    """Test that corrupted learning file is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        learn_path = tmpdir / "learn.json"

        # Write corrupted JSON
        learn_path.write_text("{ invalid json", encoding="utf-8")

        # Load should not crash
        learning = LearningEngine(learn_path=learn_path)
        learning.load()

        # Should have empty data (fallback)
        assert len(learning.data.rules) == 0
