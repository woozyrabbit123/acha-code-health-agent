"""E2E tests for ACE Python HTTP timeout rule (PY-S101)."""

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ace.export import to_json
from ace.kernel import run_analyze, run_apply, run_refactor, run_validate
from ace.skills.python import analyze_py, refactor_py_timeout

# Sample code with requests without timeout
SAMPLE_CODE_WITH_ISSUE = '''import requests

def fetch_data(host):
    """Fetch data from API without timeout."""
    return requests.get(f"http://{host}/api/data")

def post_data(url, payload):
    """Post data without timeout."""
    response = requests.post(url, json=payload)
    return response.json()
'''

# Expected code after fix
EXPECTED_FIXED_CODE = '''import requests

def fetch_data(host):
    """Fetch data from API without timeout."""
    return requests.get(f"http://{host}/api/data", timeout=10)

def post_data(url, payload):
    """Post data without timeout."""
    response = requests.post(url, json=payload, timeout=10)
    return response.json()
'''


class TestHttpTimeoutRule:
    """Tests for HTTP timeout detection and fixing."""

    def test_analyze_detects_missing_timeout(self):
        """Test that analyze detects requests calls without timeout."""
        findings = analyze_py(SAMPLE_CODE_WITH_ISSUE, "api.py")

        assert len(findings) == 2, "Should find 2 requests calls without timeout"

        # Check first finding
        assert findings[0].rule == "PY-S101-UNSAFE-HTTP"
        assert findings[0].severity == "high"
        assert findings[0].line == 5
        assert "requests.get" in findings[0].message
        assert "timeout" in findings[0].message

        # Check second finding
        assert findings[1].rule == "PY-S101-UNSAFE-HTTP"
        assert findings[1].line == 9
        assert "requests.post" in findings[1].message

    def test_refactor_adds_timeout(self):
        """Test that refactor adds timeout=10 to requests calls."""
        findings = analyze_py(SAMPLE_CODE_WITH_ISSUE, "api.py")
        refactored, plan = refactor_py_timeout(SAMPLE_CODE_WITH_ISSUE, "api.py", findings)

        # Check that timeout=10 was added
        assert "timeout=10" in refactored
        assert refactored.count("timeout=10") == 2

        # Check plan details
        assert plan.estimated_risk >= 0.75
        assert plan.rule == "PY-S101-UNSAFE-HTTP"
        assert "2 requests call" in plan.description

    def test_refactor_preserves_existing_timeout(self):
        """Test that refactor doesn't add timeout if already present."""
        code_with_timeout = 'import requests\nrequests.get("http://example.com", timeout=5)\n'
        findings = analyze_py(code_with_timeout, "api.py")

        # Should not find any issues
        assert len(findings) == 0

    def test_validate_produces_auto_decision(self):
        """Test that validate produces AUTO decision for timeout fixes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "api.py"
            test_file.write_text(SAMPLE_CODE_WITH_ISSUE, encoding="utf-8")

            # Run validation
            findings = run_analyze(str(test_file))
            plans = run_refactor(str(test_file), findings)
            receipts = run_validate(str(test_file), plans)

            assert len(receipts) == 1

            receipt = receipts[0]
            assert receipt.status == "pass"
            assert receipt.decision == "auto"  # High R* score should give AUTO
            assert receipt.parse_valid is True
            assert receipt.before_hash != receipt.after_hash

    def test_apply_writes_changes(self):
        """Test that apply successfully writes changes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "api.py"
            test_file.write_text(SAMPLE_CODE_WITH_ISSUE, encoding="utf-8")

            # Run apply
            findings = run_analyze(str(test_file))
            plans = run_refactor(str(test_file), findings)
            exit_code = run_apply(str(test_file), plans)

            assert exit_code == 0

            # Verify file was modified
            modified_content = test_file.read_text(encoding="utf-8")
            assert "timeout=10" in modified_content
            assert modified_content.count("timeout=10") == 2

    def test_apply_is_idempotent(self):
        """Test that applying twice doesn't make additional changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "api.py"
            test_file.write_text(SAMPLE_CODE_WITH_ISSUE, encoding="utf-8")

            # First apply
            findings1 = run_analyze(str(test_file))
            plans1 = run_refactor(str(test_file), findings1)
            run_apply(str(test_file), plans1)

            content_after_first = test_file.read_text(encoding="utf-8")

            # Second apply
            findings2 = run_analyze(str(test_file))
            assert len(findings2) == 0, "Should find no issues after first fix"

            plans2 = run_refactor(str(test_file), findings2)
            run_apply(str(test_file), plans2)

            content_after_second = test_file.read_text(encoding="utf-8")

            # Content should be identical
            assert content_after_first == content_after_second

    def test_determinism_across_runs(self):
        """Test that running analyze/refactor twice produces identical JSON."""
        # Run analysis twice
        findings1 = analyze_py(SAMPLE_CODE_WITH_ISSUE, "api.py")
        json1 = to_json([f.__dict__ for f in findings1])

        findings2 = analyze_py(SAMPLE_CODE_WITH_ISSUE, "api.py")
        json2 = to_json([f.__dict__ for f in findings2])

        # JSON should be byte-identical
        assert json1 == json2

        # Verify with SHA256
        hash1 = hashlib.sha256(json1.encode()).hexdigest()
        hash2 = hashlib.sha256(json2.encode()).hexdigest()
        assert hash1 == hash2

    def test_cli_analyze_works(self):
        """Test CLI analyze command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "api.py"
            test_file.write_text(SAMPLE_CODE_WITH_ISSUE, encoding="utf-8")

            # Run ace analyze via CLI
            result = subprocess.run(
                [sys.executable, "-m", "ace.cli", "analyze", "--target", str(tmpdir), "--format", "json"],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == 0
            assert "PY-S101-UNSAFE-HTTP" in result.stdout
            assert "high" in result.stdout

    def test_full_e2e_workflow(self):
        """Test full E2E: analyze → refactor → validate → apply."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "api.py"
            test_file.write_text(SAMPLE_CODE_WITH_ISSUE, encoding="utf-8")

            # Step 1: Analyze
            findings = run_analyze(str(test_file))
            assert len(findings) == 2
            assert all(f.rule == "PY-S101-UNSAFE-HTTP" for f in findings)
            assert all(f.severity == "high" for f in findings)

            # Step 2: Refactor
            plans = run_refactor(str(test_file), findings)
            assert len(plans) == 1
            assert plans[0].estimated_risk >= 0.75

            # Step 3: Validate
            receipts = run_validate(str(test_file), plans)
            assert len(receipts) == 1
            assert receipts[0].status == "pass"
            assert receipts[0].decision == "auto"
            assert receipts[0].before_hash != receipts[0].after_hash

            # Step 4: Apply
            exit_code = run_apply(str(test_file), plans)
            assert exit_code == 0

            # Step 5: Verify result
            modified_content = test_file.read_text(encoding="utf-8")
            assert "timeout=10" in modified_content

            # Step 6: Verify idempotency
            findings_after = run_analyze(str(test_file))
            assert len(findings_after) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self):
        """Test handling of empty Python file."""
        findings = analyze_py("", "empty.py")
        assert len(findings) == 0

    def test_file_with_syntax_error(self):
        """Test handling of file with syntax errors."""
        bad_code = "def foo(\n  # syntax error"
        findings = analyze_py(bad_code, "bad.py")
        # Should gracefully handle and return empty findings
        assert findings is not None

    def test_requests_with_existing_timeout(self):
        """Test that we don't flag requests calls that already have timeout."""
        code = '''import requests
def fetch():
    return requests.get("http://example.com", timeout=30)
'''
        findings = analyze_py(code, "good.py")
        assert len(findings) == 0

    def test_non_requests_calls(self):
        """Test that we don't flag non-requests calls."""
        code = '''import other_lib
def fetch():
    return other_lib.get("http://example.com")
'''
        findings = analyze_py(code, "other.py")
        assert len(findings) == 0

    def test_multiple_files_deterministic_order(self):
        """Test that analyzing multiple files produces deterministic ordering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create multiple files
            (tmpdir_path / "a.py").write_text('import requests\nrequests.get("http://a.com")\n')
            (tmpdir_path / "b.py").write_text('import requests\nrequests.post("http://b.com")\n')
            (tmpdir_path / "c.py").write_text('import requests\nrequests.put("http://c.com")\n')

            # Run twice
            findings1 = run_analyze(str(tmpdir_path))
            findings2 = run_analyze(str(tmpdir_path))

            # Should have same count and order
            assert len(findings1) == len(findings2)
            assert len(findings1) == 3

            # Files should be in sorted order
            for i in range(len(findings1)):
                assert findings1[i].file == findings2[i].file
                assert findings1[i].line == findings2[i].line


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
