"""Tests for HTML reporter Pro features"""

import tempfile
from pathlib import Path

from acha.utils.html_reporter import HTMLReporter


def test_html_report_basic():
    """Test basic HTML report generation"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.9,
                "file": "test.py",
                "start_line": 10,
                "finding": "critical_issue",
                "rationale": "This is critical",
            }
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Check basic structure
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "ACHA Code Health Report" in html
    assert "critical_issue" in html
    assert "This is critical" in html


def test_html_report_with_baseline():
    """Test HTML report with baseline comparison"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.7,
                "file": "test.py",
                "start_line": 10,
                "rule": "error_rule",
                "finding": "error_rule",
                "rationale": "New error",
            },
            {
                "severity": 0.4,
                "file": "test.py",
                "start_line": 20,
                "rule": "warning_rule",
                "finding": "warning_rule",
                "rationale": "Existing warning",
            }
        ]
    }

    baseline_comparison = {
        "new": [
            {
                "file": "test.py",
                "start_line": 10,
                "rule": "error_rule",
            }
        ],
        "existing": [
            {
                "file": "test.py",
                "start_line": 20,
                "rule": "warning_rule",
            }
        ],
        "fixed": [],
        "summary": {
            "new_count": 1,
            "existing_count": 1,
            "fixed_count": 0,
        }
    }

    html = reporter.generate(
        analysis=analysis,
        baseline_comparison=baseline_comparison
    )

    # Check baseline summary present
    assert "baseline-summary" in html
    assert "New:" in html or "🆕" in html
    assert "Existing:" in html or "📍" in html
    assert "Fixed:" in html or "✅" in html

    # Check status badges
    assert "status-badge" in html
    assert "NEW" in html or "EXISTING" in html

    # Check status filter
    assert "statusFilter" in html


def test_html_report_with_suppressed_findings():
    """Test HTML report shows suppressed findings"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.7,
                "file": "test.py",
                "start_line": 10,
                "finding": "error_rule",
                "rationale": "Suppressed error",
                "suppressed": True,
            },
            {
                "severity": 0.4,
                "file": "test.py",
                "start_line": 20,
                "finding": "warning_rule",
                "rationale": "Normal warning",
            }
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Check suppressed badge present
    assert "suppressed-badge" in html
    assert "SUPPRESSED" in html


def test_html_report_rule_filtering():
    """Test HTML report includes rule filtering"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.7,
                "file": "test.py",
                "start_line": 10,
                "finding": "unused_import",
                "rule": "unused_import",
                "rationale": "Unused import detected",
            },
            {
                "severity": 0.4,
                "file": "test.py",
                "start_line": 20,
                "finding": "magic_number",
                "rule": "magic_number",
                "rationale": "Magic number found",
            }
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Check rule filter present
    assert "ruleFilter" in html
    assert "unused_import" in html
    assert "magic_number" in html


def test_html_report_no_findings():
    """Test HTML report with no findings"""
    reporter = HTMLReporter()

    analysis = {"findings": []}

    html = reporter.generate(analysis=analysis)

    assert "No findings detected" in html or "Great job" in html


def test_html_report_self_contained():
    """Test HTML report is self-contained (no CDN links)"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.5,
                "file": "test.py",
                "start_line": 10,
                "finding": "test_issue",
                "rationale": "Test",
            }
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Should not contain CDN links
    assert "cdn.jsdelivr" not in html.lower()
    assert "unpkg.com" not in html.lower()
    assert "cdnjs.cloudflare.com" not in html.lower()

    # Should contain embedded CSS
    assert "<style>" in html
    assert "</style>" in html

    # Should contain embedded JavaScript
    assert "<script>" in html
    assert "</script>" in html


def test_html_report_write_to_file():
    """Test HTML report can be written to file"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.5,
                "file": "test.py",
                "start_line": 10,
                "finding": "test_issue",
                "rationale": "Test finding",
            }
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "report.html"

        reporter.generate_and_write(
            output_path=output_path,
            analysis=analysis,
            target_path="./test"
        )

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")

        assert "<!DOCTYPE html>" in content
        assert "test_issue" in content
        assert "Test finding" in content


def test_html_report_severity_mapping():
    """Test severity values are correctly mapped"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {"severity": 0.95, "file": "a.py", "start_line": 1, "finding": "f1", "rationale": "r1"},
            {"severity": 0.75, "file": "b.py", "start_line": 2, "finding": "f2", "rationale": "r2"},
            {"severity": 0.45, "file": "c.py", "start_line": 3, "finding": "f3", "rationale": "r3"},
            {"severity": 0.15, "file": "d.py", "start_line": 4, "finding": "f4", "rationale": "r4"},
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Check severity badges are present
    assert "severity-critical" in html
    assert "severity-error" in html
    assert "severity-warning" in html
    assert "severity-info" in html


def test_html_report_filter_functionality():
    """Test that filter controls are properly set up"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.7,
                "file": "test.py",
                "start_line": 10,
                "finding": "error_rule",
                "rule": "error_rule",
                "rationale": "Error",
            }
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Check filter elements present
    assert "findingFilter" in html
    assert "severityFilter" in html
    assert "ruleFilter" in html

    # Check filter function exists
    assert "function filterFindings()" in html or "filterFindings()" in html
    assert "addEventListener" in html


def test_html_report_table_sorting():
    """Test that table sorting functionality exists"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "severity": 0.7,
                "file": "test.py",
                "start_line": 10,
                "finding": "rule1",
                "rationale": "Finding 1",
            }
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Check sortable table headers
    assert "data-sort" in html
    assert "th" in html.lower()


def test_html_report_counts_by_severity():
    """Test that severity counts are displayed"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {"severity": 0.9, "file": "a.py", "start_line": 1, "finding": "f1", "rationale": "r1"},
            {"severity": 0.9, "file": "b.py", "start_line": 2, "finding": "f2", "rationale": "r2"},
            {"severity": 0.4, "file": "c.py", "start_line": 3, "finding": "f3", "rationale": "r3"},
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Summary cards should show counts
    assert "Critical/Errors" in html or "Warnings" in html
    # Numeric counts should be present
    assert "2" in html  # 2 critical findings
    assert "1" in html  # 1 warning
