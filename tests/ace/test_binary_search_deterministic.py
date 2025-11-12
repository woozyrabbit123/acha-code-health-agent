"""Test that binary search for failing edits is deterministic."""

import tempfile
from pathlib import Path
from dataclasses import dataclass

import pytest

from ace.guard import GuardResult
from ace.repair import try_apply_with_repair


@dataclass
class MockEdit:
    """Mock Edit object for testing."""
    file: str
    start_line: int
    end_line: int
    op: str
    payload: str


def test_binary_search_deterministic():
    """Test that binary search produces same results across runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("print('original')\n")

        # Create 5 edits: indices 1 and 3 fail, others pass
        edits = []
        for i in range(5):
            # Edits 1 and 3 have syntax errors
            if i in [1, 3]:
                payload = f"# Edit {i} - bad\nprint('bad{i}'\n"  # Missing paren
            else:
                payload = f"# Edit {i} - good\nprint('good{i}')\n"

            edits.append(MockEdit(
                file=str(file_path),
                start_line=1,
                end_line=1,
                op="replace",
                payload=payload
            ))

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

        # Run repair multiple times
        results = []
        for run in range(3):
            result = try_apply_with_repair(
                file_path=file_path,
                edits=edits,
                original_content=original_content,
                guard_fn=mock_guard,
                run_id=f"test-run-{run}"
            )
            results.append(result)

        # All runs should produce same results
        for i in range(1, len(results)):
            assert results[i].success == results[0].success
            assert results[i].partial_apply == results[0].partial_apply

            if results[i].report:
                assert results[i].report.safe_edits == results[0].report.safe_edits
                assert results[i].report.failed_edits == results[0].report.failed_edits
                # Failed indices should be consistent
                assert set(results[i].report.failed_edit_indices) == set(results[0].report.failed_edit_indices)


def test_binary_search_sorted_order():
    """Test that binary search respects edit ordering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("print('original')\n")

        # Create edits with explicit start_line ordering
        edits = [
            MockEdit(
                file=str(file_path),
                start_line=10,  # Later line
                end_line=10,
                op="replace",
                payload="print('edit1')\n"
            ),
            MockEdit(
                file=str(file_path),
                start_line=5,  # Earlier line
                end_line=5,
                op="replace",
                payload="print('edit2'\n"  # Syntax error
            ),
            MockEdit(
                file=str(file_path),
                start_line=1,  # Earliest line
                end_line=1,
                op="replace",
                payload="print('edit3')\n"
            ),
        ]

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
            run_id="test-order"
        )

        # Should successfully isolate the failing edit
        assert result.success
        assert result.partial_apply
        assert result.report is not None

        # The failing edit should be isolated
        # After sorting by start_line: [edit3(line 1), edit2(line 5), edit1(line 10)]
        # edit2 at index 1 (after sorting) should fail
        assert result.report.failed_edits == 1
        assert result.report.safe_edits == 2
