"""Tests for Exporter"""
import json
import tempfile
import zipfile
from pathlib import Path
import pytest
from jsonschema import ValidationError

from acha.utils.exporter import build_proof_pack


def test_build_proof_pack_with_all_files():
    """Test building proof pack with all files present"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create dist and reports directories
        dist_dir = tmpdir_path / "dist"
        reports_dir = tmpdir_path / "reports"
        dist_dir.mkdir()
        reports_dir.mkdir()

        # Create required JSON files with valid data
        analysis_data = {
            "findings": [
                {
                    "id": "ANL-001",
                    "file": "test.py",
                    "start_line": 1,
                    "end_line": 1,
                    "finding": "dup_immutable_const",
                    "severity": 0.5,
                    "fix_type": "inline_const",
                    "rationale": "Test finding",
                    "test_hints": ["Test hint"]
                }
            ]
        }
        with open(reports_dir / "analysis.json", 'w') as f:
            json.dump(analysis_data, f)

        patch_summary_data = {
            "patch_id": "test-patch-123",
            "files_touched": ["test.py"],
            "lines_added": 5,
            "lines_removed": 3,
            "notes": ["Test note"]
        }
        with open(reports_dir / "patch_summary.json", 'w') as f:
            json.dump(patch_summary_data, f)

        validate_data = {
            "patch_id": "test-patch-123",
            "status": "pass",
            "duration_s": 1.5,
            "tests_run": 10,
            "failing_tests": [],
            "validate_dir": "./test"
        }
        with open(reports_dir / "validate.json", 'w') as f:
            json.dump(validate_data, f)

        # Create optional files
        with open(reports_dir / "test_output.txt", 'w') as f:
            f.write("Test output content")

        with open(dist_dir / "patch.diff", 'w') as f:
            f.write("--- a/test.py\n+++ b/test.py\n")

        # Build proof pack
        zip_path = build_proof_pack(
            dist_dir=str(dist_dir),
            reports_dir=str(reports_dir),
            patch_path=str(dist_dir / "patch.diff")
        )

        # Verify ZIP was created
        assert Path(zip_path).exists(), "ZIP file should exist"
        assert Path(zip_path).is_absolute(), "Should return absolute path"

        # Verify ZIP contents
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            # Check required files
            assert "reports/analysis.json" in namelist
            assert "reports/patch_summary.json" in namelist
            assert "reports/validate.json" in namelist
            assert "reports/report.md" in namelist

            # Check optional files
            assert "reports/test_output.txt" in namelist
            assert "dist/patch.diff" in namelist

            # Verify JSON files can be loaded
            analysis_in_zip = json.loads(zf.read("reports/analysis.json"))
            assert len(analysis_in_zip["findings"]) == 1

            patch_summary_in_zip = json.loads(zf.read("reports/patch_summary.json"))
            assert patch_summary_in_zip["patch_id"] == "test-patch-123"

            validate_in_zip = json.loads(zf.read("reports/validate.json"))
            assert validate_in_zip["status"] == "pass"

            # Verify report.md content
            report_md_content = zf.read("reports/report.md").decode('utf-8')
            assert "test-patch-123" in report_md_content
            assert "pass" in report_md_content
            assert "dup_immutable_const" in report_md_content
            assert "**Files touched:** 1" in report_md_content
            assert "+5 / -3" in report_md_content

        # Verify report.md was created in reports dir
        assert (reports_dir / "report.md").exists()


def test_build_proof_pack_without_optional_files():
    """Test building proof pack without optional files"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create dist and reports directories
        dist_dir = tmpdir_path / "dist"
        reports_dir = tmpdir_path / "reports"
        dist_dir.mkdir()
        reports_dir.mkdir()

        # Create only required JSON files
        analysis_data = {"findings": []}
        with open(reports_dir / "analysis.json", 'w') as f:
            json.dump(analysis_data, f)

        patch_summary_data = {
            "patch_id": "test-patch-456",
            "files_touched": [],
            "lines_added": 0,
            "lines_removed": 0,
            "notes": []
        }
        with open(reports_dir / "patch_summary.json", 'w') as f:
            json.dump(patch_summary_data, f)

        validate_data = {
            "patch_id": "test-patch-456",
            "status": "fail",
            "duration_s": 2.0,
            "tests_run": 5,
            "failing_tests": ["test_foo"],
            "validate_dir": "./test"
        }
        with open(reports_dir / "validate.json", 'w') as f:
            json.dump(validate_data, f)

        # Build proof pack (no optional files)
        zip_path = build_proof_pack(
            dist_dir=str(dist_dir),
            reports_dir=str(reports_dir),
            patch_path=str(dist_dir / "patch.diff")  # doesn't exist
        )

        # Verify ZIP was created
        assert Path(zip_path).exists()

        # Verify ZIP contents
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            # Check required files
            assert "reports/analysis.json" in namelist
            assert "reports/patch_summary.json" in namelist
            assert "reports/validate.json" in namelist
            assert "reports/report.md" in namelist

            # Check optional files are NOT present
            assert "reports/test_output.txt" not in namelist
            assert "dist/patch.diff" not in namelist


def test_build_proof_pack_missing_required_file():
    """Test that build_proof_pack fails if required JSON is missing"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create dist and reports directories
        dist_dir = tmpdir_path / "dist"
        reports_dir = tmpdir_path / "reports"
        dist_dir.mkdir()
        reports_dir.mkdir()

        # Create only some files (missing analysis.json)
        patch_summary_data = {
            "patch_id": "test",
            "files_touched": [],
            "lines_added": 0,
            "lines_removed": 0,
            "notes": []
        }
        with open(reports_dir / "patch_summary.json", 'w') as f:
            json.dump(patch_summary_data, f)

        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="analysis.json"):
            build_proof_pack(
                dist_dir=str(dist_dir),
                reports_dir=str(reports_dir)
            )


def test_build_proof_pack_invalid_json():
    """Test that build_proof_pack fails on invalid JSON schema"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create dist and reports directories
        dist_dir = tmpdir_path / "dist"
        reports_dir = tmpdir_path / "reports"
        dist_dir.mkdir()
        reports_dir.mkdir()

        # Create invalid analysis.json (missing required field)
        invalid_analysis = {"findings": [{"id": "x"}]}  # missing required fields
        with open(reports_dir / "analysis.json", 'w') as f:
            json.dump(invalid_analysis, f)

        patch_summary_data = {
            "patch_id": "test",
            "files_touched": [],
            "lines_added": 0,
            "lines_removed": 0,
            "notes": []
        }
        with open(reports_dir / "patch_summary.json", 'w') as f:
            json.dump(patch_summary_data, f)

        validate_data = {
            "patch_id": "test",
            "status": "pass",
            "duration_s": 1.0,
            "tests_run": 0,
            "failing_tests": [],
            "validate_dir": "."
        }
        with open(reports_dir / "validate.json", 'w') as f:
            json.dump(validate_data, f)

        # Should raise ValidationError
        with pytest.raises(ValidationError):
            build_proof_pack(
                dist_dir=str(dist_dir),
                reports_dir=str(reports_dir)
            )


def test_report_md_generation():
    """Test that report.md is generated correctly"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create dist and reports directories
        dist_dir = tmpdir_path / "dist"
        reports_dir = tmpdir_path / "reports"
        dist_dir.mkdir()
        reports_dir.mkdir()

        # Create JSON files with specific data
        analysis_data = {
            "findings": [
                {
                    "id": "ANL-001",
                    "file": "test.py",
                    "start_line": 1,
                    "end_line": 1,
                    "finding": "risky_construct",
                    "severity": 0.9,
                    "fix_type": "remove",
                    "rationale": "Test",
                    "test_hints": []
                },
                {
                    "id": "ANL-002",
                    "file": "test.py",
                    "start_line": 2,
                    "end_line": 2,
                    "finding": "risky_construct",
                    "severity": 0.8,
                    "fix_type": "remove",
                    "rationale": "Test",
                    "test_hints": []
                },
                {
                    "id": "ANL-003",
                    "file": "test.py",
                    "start_line": 3,
                    "end_line": 3,
                    "finding": "dup_immutable_const",
                    "severity": 0.4,
                    "fix_type": "inline",
                    "rationale": "Test",
                    "test_hints": []
                }
            ]
        }
        with open(reports_dir / "analysis.json", 'w') as f:
            json.dump(analysis_data, f)

        patch_summary_data = {
            "patch_id": "PATCH-XYZ-789",
            "files_touched": ["file1.py", "file2.py", "file3.py"],
            "lines_added": 42,
            "lines_removed": 13,
            "notes": []
        }
        with open(reports_dir / "patch_summary.json", 'w') as f:
            json.dump(patch_summary_data, f)

        validate_data = {
            "patch_id": "PATCH-XYZ-789",
            "status": "pass",
            "duration_s": 3.14,
            "tests_run": 25,
            "failing_tests": [],
            "validate_dir": "."
        }
        with open(reports_dir / "validate.json", 'w') as f:
            json.dump(validate_data, f)

        # Build proof pack
        build_proof_pack(
            dist_dir=str(dist_dir),
            reports_dir=str(reports_dir)
        )

        # Read and verify report.md
        report_md = (reports_dir / "report.md").read_text()

        # Check key information
        assert "PATCH-XYZ-789" in report_md
        assert "**Files touched:** 3" in report_md
        assert "+42 / -13" in report_md
        assert "Findings: 3" in report_md
        assert "risky_construct: 2" in report_md
        assert "dup_immutable_const: 1" in report_md
        assert "Status: pass" in report_md
        assert "Tests run: 25" in report_md
        assert "Duration: 3.14s" in report_md
        assert "Generated by ACHA exporter" in report_md
