"""Tests for ACE baseline system."""

import json
import tempfile
from pathlib import Path

from ace.kernel import run_analyze
from ace.storage import compare_baseline, load_baseline, save_baseline


def test_baseline_save_and_load():
    """Test saving and loading baseline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        findings = [
            {
                "stable_id": "abc123",
                "rule": "PY-TEST-01",
                "severity": "high",
                "file": "test.py",
                "message": "Test finding",
                "line": 1,
            },
            {
                "stable_id": "def456",
                "rule": "PY-TEST-02",
                "severity": "medium",
                "file": "test2.py",
                "message": "Another finding",
                "line": 5,
            },
        ]

        # Save baseline
        result = save_baseline(findings, baseline_path)
        assert result is True
        assert baseline_path.exists()

        # Load baseline
        loaded = load_baseline(baseline_path)
        assert len(loaded) == 2
        assert loaded[0]["stable_id"] == "abc123"
        assert loaded[1]["stable_id"] == "def456"


def test_baseline_deterministic_format():
    """Test that baseline JSON is deterministic (sorted keys, sorted findings)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        # Create findings in non-sorted order
        findings = [
            {"stable_id": "zzz", "rule": "R3", "severity": "low", "file": "c.py", "message": "C"},
            {"stable_id": "aaa", "rule": "R1", "severity": "high", "file": "a.py", "message": "A"},
            {"stable_id": "mmm", "rule": "R2", "severity": "medium", "file": "b.py", "message": "B"},
        ]

        save_baseline(findings, baseline_path)

        # Read raw JSON
        with open(baseline_path, encoding="utf-8") as f:
            content = f.read()

        # Parse and verify sorting
        parsed = json.loads(content)
        assert parsed[0]["stable_id"] == "aaa"  # Sorted by stable_id
        assert parsed[1]["stable_id"] == "mmm"
        assert parsed[2]["stable_id"] == "zzz"

        # Verify keys are sorted (check JSON string)
        assert '"file"' in content
        assert '"message"' in content
        assert '"rule"' in content
        assert '"severity"' in content
        assert '"stable_id"' in content


def test_baseline_compare_no_changes():
    """Test baseline comparison with no changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "A"},
        ]

        save_baseline(findings, baseline_path)

        # Compare identical findings
        comparison = compare_baseline(findings, baseline_path)

        assert len(comparison["added"]) == 0
        assert len(comparison["removed"]) == 0
        assert len(comparison["changed"]) == 0
        assert len(comparison["existing"]) == 1


def test_baseline_compare_added_findings():
    """Test baseline comparison with added findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        baseline_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "A"},
        ]
        save_baseline(baseline_findings, baseline_path)

        # Current has additional finding
        current_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "A"},
            {"stable_id": "xyz", "rule": "R2", "severity": "low", "file": "b.py", "message": "B"},
        ]

        comparison = compare_baseline(current_findings, baseline_path)

        assert len(comparison["added"]) == 1
        assert comparison["added"][0]["stable_id"] == "xyz"
        assert len(comparison["removed"]) == 0
        assert len(comparison["existing"]) == 1


def test_baseline_compare_removed_findings():
    """Test baseline comparison with removed findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        baseline_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "A"},
            {"stable_id": "xyz", "rule": "R2", "severity": "low", "file": "b.py", "message": "B"},
        ]
        save_baseline(baseline_findings, baseline_path)

        # Current is missing one finding
        current_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "A"},
        ]

        comparison = compare_baseline(current_findings, baseline_path)

        assert len(comparison["added"]) == 0
        assert len(comparison["removed"]) == 1
        assert comparison["removed"][0]["stable_id"] == "xyz"
        assert len(comparison["existing"]) == 1


def test_baseline_compare_changed_severity():
    """Test baseline comparison with changed severity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        baseline_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "A"},
        ]
        save_baseline(baseline_findings, baseline_path)

        # Current has different severity
        current_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "medium", "file": "a.py", "message": "A"},
        ]

        comparison = compare_baseline(current_findings, baseline_path)

        assert len(comparison["added"]) == 0
        assert len(comparison["removed"]) == 0
        assert len(comparison["changed"]) == 1
        assert comparison["changed"][0]["stable_id"] == "abc"
        assert comparison["changed"][0]["baseline"]["severity"] == "high"
        assert comparison["changed"][0]["current"]["severity"] == "medium"


def test_baseline_compare_changed_message():
    """Test baseline comparison with changed message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        baseline_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "Old message"},
        ]
        save_baseline(baseline_findings, baseline_path)

        # Current has different message
        current_findings = [
            {"stable_id": "abc", "rule": "R1", "severity": "high", "file": "a.py", "message": "New message"},
        ]

        comparison = compare_baseline(current_findings, baseline_path)

        assert len(comparison["changed"]) == 1
        assert comparison["changed"][0]["baseline"]["message"] == "Old message"
        assert comparison["changed"][0]["current"]["message"] == "New message"


def test_baseline_load_nonexistent():
    """Test loading nonexistent baseline returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "nonexistent.json"
        loaded = load_baseline(baseline_path)
        assert loaded == []


def test_baseline_end_to_end():
    """Test baseline workflow end-to-end."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files with findings
        test_file1 = Path(tmpdir) / "test1.py"
        test_file1.write_text("import os\n", encoding="utf-8")

        baseline_path = Path(tmpdir) / "baseline.json"

        # Step 1: Create baseline
        findings_v1 = run_analyze(tmpdir, use_cache=False)
        findings_v1_dicts = [f.to_dict() for f in findings_v1]
        save_baseline(findings_v1_dicts, baseline_path)

        assert baseline_path.exists()
        initial_count = len(findings_v1)

        # Step 2: No changes - compare should show no differences
        findings_v2 = run_analyze(tmpdir, use_cache=False)
        findings_v2_dicts = [f.to_dict() for f in findings_v2]
        comparison = compare_baseline(findings_v2_dicts, baseline_path)

        assert len(comparison["added"]) == 0
        assert len(comparison["removed"]) == 0
        assert len(comparison["existing"]) == initial_count

        # Step 3: Add a new file - compare should detect new findings
        test_file2 = Path(tmpdir) / "test2.py"
        test_file2.write_text("import subprocess\nsubprocess.run(['ls'])\n", encoding="utf-8")

        findings_v3 = run_analyze(tmpdir, use_cache=False)
        findings_v3_dicts = [f.to_dict() for f in findings_v3]
        comparison = compare_baseline(findings_v3_dicts, baseline_path)

        # Should have at least one added finding from test2.py
        assert len(comparison["added"]) > 0
        assert any("test2.py" in f["file"] for f in comparison["added"])


def test_baseline_deterministic_on_rerun():
    """Test that baseline creation is deterministic on multiple runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("import os\nimport sys\n", encoding="utf-8")

        baseline_path1 = Path(tmpdir) / "baseline1.json"
        baseline_path2 = Path(tmpdir) / "baseline2.json"

        # Create baseline twice
        findings1 = run_analyze(tmpdir, use_cache=False)
        save_baseline([f.to_dict() for f in findings1], baseline_path1)

        findings2 = run_analyze(tmpdir, use_cache=False)
        save_baseline([f.to_dict() for f in findings2], baseline_path2)

        # Baselines should be byte-identical
        content1 = baseline_path1.read_text()
        content2 = baseline_path2.read_text()
        assert content1 == content2


def test_baseline_only_stores_required_fields():
    """Test that baseline only stores required fields (stable_id, rule, severity, file, message)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_path = Path(tmpdir) / "baseline.json"

        findings = [
            {
                "stable_id": "abc",
                "rule": "R1",
                "severity": "high",
                "file": "a.py",
                "message": "Test",
                "line": 42,
                "snippet": "some code",
                "suggestion": "fix this",
                "extra_field": "should not be stored",
            }
        ]

        save_baseline(findings, baseline_path)

        # Load and verify only required fields are present
        loaded = load_baseline(baseline_path)
        entry = loaded[0]

        assert "stable_id" in entry
        assert "rule" in entry
        assert "severity" in entry
        assert "file" in entry
        assert "message" in entry
        assert "extra_field" not in entry
        assert "line" not in entry  # line is not stored in baseline
        assert "snippet" not in entry
        assert "suggestion" not in entry
