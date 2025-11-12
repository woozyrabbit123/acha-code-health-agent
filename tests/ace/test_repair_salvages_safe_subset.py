"""Test that repair salvages safe subset of edits."""

import tempfile
from pathlib import Path
from dataclasses import dataclass

import pytest

from ace.guard import GuardResult
from ace.repair import try_apply_with_repair
from ace.skills.python import Edit


@dataclass
class MockEdit:
    """Mock Edit object for testing."""
    file: str
    start_line: int
    end_line: int
    op: str
    payload: str


def test_repair_salvages_safe_subset():
    """Test that repair isolates failing edit and applies safe ones."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("print('original')\n")

        # Create three edits: two safe, one bad
        edit1 = MockEdit(
            file=str(file_path),
            start_line=1,
            end_line=1,
            op="replace",
            payload="# Safe edit 1\nprint('safe1')\n"
        )

        edit2 = MockEdit(
            file=str(file_path),
            start_line=1,
            end_line=1,
            op="replace",
            payload="# Bad edit - syntax error\nprint('bad'\n"  # Missing closing paren
        )

        edit3 = MockEdit(
            file=str(file_path),
            start_line=1,
            end_line=1,
            op="replace",
            payload="# Safe edit 3\nprint('safe3')\n"
        )

        edits = [edit1, edit2, edit3]
        original_content = "print('original')\n"

        # Mock guard function that fails on syntax errors
        def mock_guard(path, before, after):
            # Check if the content has balanced parentheses
            if after.count("(") != after.count(")"):
                return GuardResult(
                    passed=False,
                    file=str(path),
                    before_content=before,
                    after_content=after,
                    guard_type="parse",
                    errors=["Syntax error: unmatched parentheses"]
                )
            return GuardResult(
                passed=True,
                file=str(path),
                before_content=before,
                after_content=after,
                guard_type="parse",
                errors=[]
            )

        # Run repair
        result = try_apply_with_repair(
            file_path=file_path,
            edits=edits,
            original_content=original_content,
            guard_fn=mock_guard,
            run_id="test-run-123"
        )

        # Should successfully apply safe subset
        assert result.success
        assert result.partial_apply
        assert result.report is not None

        # Report should show 2 safe, 1 failed
        assert result.report.total_edits == 3
        assert result.report.failed_edits == 1
        assert result.report.safe_edits == 2

        # Content should have safe edits applied (last safe edit wins in mock)
        assert "print" in result.content


def test_repair_all_edits_fail():
    """Test that repair handles case where all edits fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("print('original')\n")

        # Create edit that always fails
        edit1 = MockEdit(
            file=str(file_path),
            start_line=1,
            end_line=1,
            op="replace",
            payload="# Bad syntax\nprint('bad'\n"  # Missing closing paren
        )

        edits = [edit1]
        original_content = "print('original')\n"

        def mock_guard(path, before, after):
            if after.count("(") != after.count(")"):
                return GuardResult(
                    passed=False,
                    file=str(path),
                    before_content=before,
                    after_content=after,
                    guard_type="parse",
                    errors=["Syntax error"]
                )
            return GuardResult(
                passed=True,
                file=str(path),
                before_content=before,
                after_content=after,
                guard_type="parse",
                errors=[]
            )

        result = try_apply_with_repair(
            file_path=file_path,
            edits=edits,
            original_content=original_content,
            guard_fn=mock_guard,
            run_id="test-run-456"
        )

        # Should fail and return original content
        assert not result.success
        assert result.content == original_content
        assert result.report is not None
        assert result.report.safe_edits == 0
        assert result.report.failed_edits == 1


def test_repair_all_edits_pass():
    """Test that repair succeeds when all edits pass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("print('original')\n")

        edit1 = MockEdit(
            file=str(file_path),
            start_line=1,
            end_line=1,
            op="replace",
            payload="print('modified')\n"
        )

        edits = [edit1]
        original_content = "print('original')\n"

        def mock_guard(path, before, after):
            # All edits pass
            return GuardResult(
                passed=True,
                file=str(path),
                before_content=before,
                after_content=after,
                guard_type="parse",
                errors=[]
            )

        result = try_apply_with_repair(
            file_path=file_path,
            edits=edits,
            original_content=original_content,
            guard_fn=mock_guard,
            run_id="test-run-789"
        )

        # Should succeed without partial apply
        assert result.success
        assert not result.partial_apply
        assert result.report is None
        assert "modified" in result.content
