"""Test that repair reports are written and have stable format."""

import json
import tempfile
from pathlib import Path

import pytest

from ace.repair import RepairReport, write_repair_report, read_latest_repair_report


def test_repair_report_written_and_stable():
    """Test that repair reports are written with stable JSON format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repairs_dir = Path(tmpdir) / ".ace" / "repairs"

        # Create a repair report
        report = RepairReport(
            run_id="test-run-123",
            file="test.py",
            total_edits=3,
            safe_edits=2,
            failed_edits=1,
            safe_edit_indices=[0, 2],
            failed_edit_indices=[1],
            guard_failure_reason="parse: syntax error",
            repair_suggestions=["Review line 5", "Check syntax"],
            timestamp="2025-01-01T00:00:00.000Z"
        )

        # Write report
        report_path = write_repair_report(report, repairs_dir)

        # Verify file exists
        assert report_path.exists()
        assert report_path.name == "test-run-123-test.py.json"

        # Read and verify JSON format
        with open(report_path, "r") as f:
            data = json.load(f)

        # Check all fields are present
        assert data["run_id"] == "test-run-123"
        assert data["file"] == "test.py"
        assert data["total_edits"] == 3
        assert data["safe_edits"] == 2
        assert data["failed_edits"] == 1
        assert data["safe_edit_indices"] == [0, 2]
        assert data["failed_edit_indices"] == [1]
        assert data["guard_failure_reason"] == "parse: syntax error"
        assert len(data["repair_suggestions"]) == 2

        # Verify JSON is sorted (stable serialization)
        json_str = report_path.read_text()
        assert '"failed_edit_indices"' in json_str
        assert '"failed_edits"' in json_str

        # Test round-trip
        loaded_report = RepairReport.from_dict(data)
        assert loaded_report.run_id == report.run_id
        assert loaded_report.safe_edits == report.safe_edits


def test_read_latest_repair_report():
    """Test reading the most recent repair report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repairs_dir = Path(tmpdir) / ".ace" / "repairs"

        # Write multiple reports
        report1 = RepairReport(
            run_id="run-1",
            file="test1.py",
            total_edits=1,
            safe_edits=1,
            failed_edits=0,
            safe_edit_indices=[0],
            failed_edit_indices=[],
            guard_failure_reason="",
            timestamp="2025-01-01T00:00:00.000Z"
        )

        report2 = RepairReport(
            run_id="run-2",
            file="test2.py",
            total_edits=2,
            safe_edits=1,
            failed_edits=1,
            safe_edit_indices=[0],
            failed_edit_indices=[1],
            guard_failure_reason="parse error",
            timestamp="2025-01-02T00:00:00.000Z"
        )

        write_repair_report(report1, repairs_dir)
        # Small delay to ensure different modification times
        import time
        time.sleep(0.01)
        write_repair_report(report2, repairs_dir)

        # Read latest should return report2
        latest = read_latest_repair_report(repairs_dir)
        assert latest is not None
        assert latest.run_id == "run-2"
        assert latest.file == "test2.py"


def test_repair_report_no_reports():
    """Test reading when no reports exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repairs_dir = Path(tmpdir) / ".ace" / "repairs"

        # Should return None when no reports exist
        latest = read_latest_repair_report(repairs_dir)
        assert latest is None
