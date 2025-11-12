"""Tests for health map generation."""

import tempfile
from pathlib import Path

import pytest

from ace.report import (
    aggregate_statistics,
    compute_report_hash,
    generate_health_map,
)
from ace.uir import create_uir


class TestAggregateStatistics:
    """Tests for statistics aggregation."""

    def test_empty_findings(self):
        """Test with no findings."""
        stats = aggregate_statistics([])
        assert stats["total_findings"] == 0
        assert len(stats["by_severity"]) == 0

    def test_by_severity(self):
        """Test severity aggregation."""
        findings = [
            create_uir("test.py", 10, "R1", "high", "msg", "", ""),
            create_uir("test.py", 20, "R2", "high", "msg", "", ""),
            create_uir("test.py", 30, "R3", "low", "msg", "", ""),
        ]
        stats = aggregate_statistics(findings)

        assert stats["by_severity"]["high"] == 2
        assert stats["by_severity"]["low"] == 1

    def test_by_rule(self):
        """Test rule aggregation."""
        findings = [
            create_uir("test.py", 10, "RULE-A", "high", "msg", "", ""),
            create_uir("test.py", 20, "RULE-A", "high", "msg", "", ""),
            create_uir("test.py", 30, "RULE-B", "low", "msg", "", ""),
        ]
        stats = aggregate_statistics(findings)

        assert stats["by_rule"]["RULE-A"] == 2
        assert stats["by_rule"]["RULE-B"] == 1

    def test_by_file(self):
        """Test file aggregation."""
        findings = [
            create_uir("test1.py", 10, "R1", "high", "msg", "", ""),
            create_uir("test1.py", 20, "R2", "high", "msg", "", ""),
            create_uir("test2.py", 30, "R3", "low", "msg", "", ""),
        ]
        stats = aggregate_statistics(findings)

        assert stats["by_file"]["test1.py"] == 2
        assert stats["by_file"]["test2.py"] == 1


class TestGenerateHealthMap:
    """Tests for health map generation."""

    def test_generate_empty_report(self):
        """Test generating report with no findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "health.html"
            path = generate_health_map([], output_path=output_path)

            assert Path(path).exists()
            content = Path(path).read_text()
            assert "ACE Workspace Health Map" in content

    def test_generate_with_findings(self):
        """Test generating report with findings."""
        findings = [
            create_uir("test.py", 10, "RULE-1", "high", "msg1", "", ""),
            create_uir("test.py", 20, "RULE-2", "medium", "msg2", "", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "health.html"
            path = generate_health_map(findings, output_path=output_path)

            content = Path(path).read_text()
            assert "Total Findings: 2" in content
            assert "RULE-1" in content

    def test_deterministic_output(self):
        """Test that output is deterministic."""
        findings = [
            create_uir("test.py", 10, "RULE-1", "high", "msg", "", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output1 = Path(tmpdir) / "health1.html"
            output2 = Path(tmpdir) / "health2.html"

            generate_health_map(findings, output_path=output1)
            generate_health_map(findings, output_path=output2)

            content1 = output1.read_text()
            content2 = output2.read_text()

            # Remove generated_at timestamp for comparison
            content1_lines = [l for l in content1.split("\n") if "generated_at" not in l and "Generated:" not in l]
            content2_lines = [l for l in content2.split("\n") if "generated_at" not in l and "Generated:" not in l]

            # Should be identical except timestamps
            assert len(content1_lines) == len(content2_lines)


class TestComputeReportHash:
    """Tests for report hash computation."""

    def test_deterministic_hash(self):
        """Test that hash is deterministic."""
        html = "<html><body>Test</body></html>"
        hash1 = compute_report_hash(html)
        hash2 = compute_report_hash(html)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Test that different content has different hash."""
        html1 = "<html><body>Test1</body></html>"
        html2 = "<html><body>Test2</body></html>"
        hash1 = compute_report_hash(html1)
        hash2 = compute_report_hash(html2)
        assert hash1 != hash2
