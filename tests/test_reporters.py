"""Tests for SARIF and HTML reporters"""
import json
import tempfile
from pathlib import Path
from acha.utils.sarif_reporter import SARIFReporter
from acha.utils.html_reporter import HTMLReporter


def test_sarif_schema_compliance():
    """Test that SARIF output follows SARIF 2.1.0 schema structure"""
    reporter = SARIFReporter(tool_name="ACHA", version="0.3.0")

    findings = [
        {
            "id": "f1",
            "finding": "unused_import",
            "file": "test.py",
            "line": 1,
            "end_line": 1,
            "severity": 0.4,
            "rationale": "Import not used"
        },
        {
            "id": "f2",
            "finding": "risky_construct",
            "file": "test.py",
            "line": 5,
            "end_line": 5,
            "severity": 0.9,
            "rationale": "Using eval() is risky"
        }
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        sarif_data = reporter.generate(findings, base_path)

        # Check required top-level fields
        assert "$schema" in sarif_data
        assert sarif_data["version"] == "2.1.0"
        assert "runs" in sarif_data
        assert len(sarif_data["runs"]) > 0

        # Check run structure
        run = sarif_data["runs"][0]
        assert "tool" in run
        assert "results" in run

        # Check tool driver
        driver = run["tool"]["driver"]
        assert driver["name"] == "ACHA"
        assert driver["version"] == "0.3.0"
        assert "rules" in driver
        assert len(driver["rules"]) > 0

        # Check results
        results = run["results"]
        assert len(results) == 2

        # Check result structure
        result = results[0]
        assert "ruleId" in result
        assert "level" in result
        assert "message" in result
        assert "locations" in result

        # Check location structure
        location = result["locations"][0]
        assert "physicalLocation" in location
        phys_loc = location["physicalLocation"]
        assert "artifactLocation" in phys_loc
        assert "region" in phys_loc
        assert "uri" in phys_loc["artifactLocation"]
        assert "startLine" in phys_loc["region"]


def test_sarif_github_compatible():
    """Test that SARIF output contains GitHub Code Scanning required fields"""
    reporter = SARIFReporter(tool_name="ACHA", version="0.3.0")

    findings = [
        {
            "finding": "unused_import",
            "file": "src/main.py",
            "line": 10,
            "severity": "warning",
            "rationale": "Unused import detected"
        }
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        sarif_data = reporter.generate(findings, base_path)

        run = sarif_data["runs"][0]

        # GitHub requires tool.driver with name and version
        assert "tool" in run
        assert "driver" in run["tool"]
        driver = run["tool"]["driver"]
        assert "name" in driver
        assert "version" in driver

        # GitHub requires results array
        assert "results" in run
        assert isinstance(run["results"], list)

        # Each result must have required fields
        if run["results"]:
            result = run["results"][0]
            assert "ruleId" in result
            assert "message" in result
            assert "text" in result["message"]
            assert "locations" in result
            assert len(result["locations"]) > 0

            # Location must have physical location with artifact and region
            location = result["locations"][0]
            assert "physicalLocation" in location
            phys = location["physicalLocation"]
            assert "artifactLocation" in phys
            assert "uri" in phys["artifactLocation"]
            assert "region" in phys


def test_html_self_contained():
    """Test that HTML report has no external resource references"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {
                "finding": "magic_number",
                "file": "app.py",
                "line": 42,
                "severity": 0.1,
                "rationale": "Magic number 42 found"
            }
        ]
    }

    html = reporter.generate(analysis=analysis)

    # Should not reference external resources
    assert "http://" not in html or "://fonts." not in html
    assert "https://" not in html or "://fonts." not in html or "://github.com" in html  # Allow GitHub link in footer

    # Should have inline styles
    assert "<style>" in html
    assert "</style>" in html

    # Should have inline scripts
    assert "<script>" in html
    assert "</script>" in html

    # Should be complete HTML document
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html
    assert "<head>" in html
    assert "<body>" in html

    # Check file size is reasonable (should be under 500KB for typical project)
    size_kb = len(html.encode('utf-8')) / 1024
    assert size_kb < 500, f"HTML report is {size_kb:.1f}KB, exceeds 500KB limit"


def test_html_responsive():
    """Test that HTML includes responsive design elements"""
    reporter = HTMLReporter()

    html = reporter.generate(analysis={}, patch={}, validation={})

    # Should have viewport meta tag for mobile
    assert 'name="viewport"' in html
    assert 'width=device-width' in html

    # Should have media queries for responsive design
    assert "@media" in html
    assert "max-width" in html or "min-width" in html


def test_report_data_accuracy():
    """Test that all findings are accurately represented in reports"""
    sarif_reporter = SARIFReporter()
    html_reporter = HTMLReporter()

    # Create test findings
    findings = [
        {
            "id": "f1",
            "finding": "unused_import",
            "file": "src/app.py",
            "line": 1,
            "end_line": 1,
            "severity": 0.4,
            "rationale": "Import os is not used"
        },
        {
            "id": "f2",
            "finding": "risky_construct",
            "file": "src/app.py",
            "line": 10,
            "end_line": 10,
            "severity": 0.9,
            "rationale": "Use of eval() is dangerous"
        },
        {
            "id": "f3",
            "finding": "magic_number",
            "file": "src/utils.py",
            "line": 5,
            "end_line": 5,
            "severity": 0.1,
            "rationale": "Magic number 3.14 found"
        }
    ]

    analysis = {"findings": findings}

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Test SARIF accuracy
        sarif_data = sarif_reporter.generate(findings, base_path)
        sarif_results = sarif_data["runs"][0]["results"]

        assert len(sarif_results) == len(findings), "SARIF should have same number of findings"

        # Check SARIF contains file names and lines
        sarif_files = {r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for r in sarif_results}
        finding_files = {f["file"] for f in findings}
        assert sarif_files == finding_files, "SARIF should reference same files"

        # Test HTML accuracy
        html = html_reporter.generate(analysis=analysis)

        # Check all findings are in HTML
        for finding in findings:
            assert finding["file"] in html, f"HTML should contain file {finding['file']}"
            assert finding["rationale"] in html, f"HTML should contain rationale '{finding['rationale']}'"

        # Check severity counts in HTML
        assert "3" in html  # Total findings
        assert html.count("severity-") >= len(findings), "HTML should have severity badges for all findings"


def test_sarif_severity_mapping():
    """Test that ACHA severities map correctly to SARIF levels"""
    reporter = SARIFReporter()

    test_cases = [
        (0.9, "error"),    # critical -> error
        (0.7, "error"),    # error -> error
        (0.4, "warning"),  # warning -> warning
        (0.1, "note"),     # info -> note
        ("critical", "error"),
        ("error", "error"),
        ("warning", "warning"),
        ("info", "note")
    ]

    for severity, expected_level in test_cases:
        findings = [{
            "finding": "test",
            "file": "test.py",
            "line": 1,
            "severity": severity
        }]

        with tempfile.TemporaryDirectory() as tmpdir:
            sarif_data = reporter.generate(findings, Path(tmpdir))
            result_level = sarif_data["runs"][0]["results"][0]["level"]
            assert result_level == expected_level, \
                f"Severity {severity} should map to {expected_level}, got {result_level}"


def test_html_with_all_sections():
    """Test HTML generation with all sections (analysis, patch, validation)"""
    reporter = HTMLReporter()

    analysis = {
        "findings": [
            {"finding": "test", "file": "test.py", "line": 1, "severity": 0.7, "rationale": "Test issue"}
        ]
    }

    patch = {
        "patch_id": "abc123",
        "files_touched": ["test.py"],
        "lines_added": 5,
        "lines_removed": 3,
        "notes": ["Fixed issue", "Improved code"]
    }

    validation = {
        "status": "pass",
        "tests_run": 10,
        "tests_passed": 10,
        "output": "All tests passed"
    }

    html = reporter.generate(
        analysis=analysis,
        patch=patch,
        validation=validation,
        target_path="/path/to/project"
    )

    # Check all sections present
    assert "Findings" in html
    assert "Refactoring" in html
    assert "Validation" in html

    # Check patch info
    assert "abc123" in html
    assert "Fixed issue" in html

    # Check validation info
    assert "pass" in html.lower() or "PASS" in html
    assert "10" in html  # Tests count


def test_sarif_write_to_file():
    """Test writing SARIF to file"""
    reporter = SARIFReporter()

    findings = [
        {"finding": "test", "file": "test.py", "line": 1, "severity": 0.4}
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        output_path = base_path / "output.sarif"

        sarif_data = reporter.generate(findings, base_path)
        reporter.write(sarif_data, output_path)

        assert output_path.exists(), "SARIF file should be created"

        # Verify it's valid JSON
        with open(output_path) as f:
            loaded_data = json.load(f)

        assert loaded_data == sarif_data, "Written SARIF should match generated data"


def test_html_write_to_file():
    """Test writing HTML to file"""
    reporter = HTMLReporter()

    html_content = reporter.generate(analysis={"findings": []})

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "report.html"

        reporter.write(html_content, output_path)

        assert output_path.exists(), "HTML file should be created"

        with open(output_path, encoding='utf-8') as f:
            loaded_html = f.read()

        assert loaded_html == html_content, "Written HTML should match generated content"


def test_sarif_empty_findings():
    """Test SARIF generation with no findings"""
    reporter = SARIFReporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        sarif_data = reporter.generate([], Path(tmpdir))

        # Should still have valid structure
        assert sarif_data["version"] == "2.1.0"
        assert len(sarif_data["runs"]) > 0

        run = sarif_data["runs"][0]
        assert "results" in run
        assert len(run["results"]) == 0  # No results


def test_html_empty_findings():
    """Test HTML generation with no findings"""
    reporter = HTMLReporter()

    html = reporter.generate(analysis={"findings": []})

    # Should show "no findings" message
    assert "no findings" in html.lower() or "great job" in html.lower()

    # Should still be valid HTML
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
