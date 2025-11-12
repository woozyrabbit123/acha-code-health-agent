"""Tests for PY-E201-BROAD-EXCEPT rule."""

import tempfile
from pathlib import Path

from ace.kernel import run_analyze, run_apply, run_refactor
from ace.skills.python import validate_python_syntax


class TestBroadExcept:
    """Test PY-E201-BROAD-EXCEPT rule."""

    def test_analyze_detects_bare_except(self):
        """Test that bare except clauses are detected."""
        code = """import os

def process_data(value):
    try:
        result = int(value)
        return result
    except:
        pass
    return None

def another_function():
    try:
        data = open("file.txt").read()
    except:
        data = ""
    return data
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            findings = run_analyze(Path(tmpdir))

            # Should find 2 bare except clauses
            bare_except_findings = [
                f for f in findings if f.rule == "PY-E201-BROAD-EXCEPT"
            ]
            assert len(bare_except_findings) == 2
            assert all(f.severity.value == "medium" for f in bare_except_findings)
            assert all("bare except" in f.message for f in bare_except_findings)

    def test_refactor_fixes_bare_except(self):
        """Test that bare except is fixed to except Exception:."""
        code = """def foo():
    try:
        risky_operation()
    except:
        pass
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            assert len(plans) == 1
            plan = plans[0]
            assert len(plan.edits) == 1
            edit = plan.edits[0]

            # Check that refactored code has "except Exception:"
            assert "except Exception:" in edit.payload
            assert "except:" not in edit.payload or "except Exception:" in edit.payload

            # Verify valid syntax
            assert validate_python_syntax(edit.payload)

    def test_apply_writes_changes(self):
        """Test that applying changes writes the file."""
        code = """def bar():
    try:
        x = 1/0
    except:
        x = 0
    return x
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            # Apply the refactoring
            result, _ = run_apply(Path(tmpdir), dry_run=False)
            assert result == 0

            # Read the modified file
            modified_content = test_file.read_text()

            # Check that the file now has "except Exception:"
            assert "except Exception:" in modified_content
            assert validate_python_syntax(modified_content)

    def test_idempotency(self):
        """Test that applying twice produces same result."""
        code = """def baz():
    try:
        value = int("abc")
    except:
        value = 0
    return value
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            # Apply once
            result1, _ = run_apply(Path(tmpdir), dry_run=False)
            assert result1 == 0

            first_content = test_file.read_text()

            # Apply again
            result2, _ = run_apply(Path(tmpdir), dry_run=False)
            assert result2 == 0

            second_content = test_file.read_text()

            # Content should be the same
            assert first_content == second_content

    def test_no_false_positives(self):
        """Test that proper except clauses are not flagged."""
        code = """def correct_function():
    try:
        value = int("123")
    except ValueError:
        value = 0
    except (TypeError, AttributeError):
        value = -1
    except Exception as e:
        value = -2
    return value
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            findings = run_analyze(Path(tmpdir))

            # Should not find any bare except
            bare_except_findings = [
                f for f in findings if f.rule == "PY-E201-BROAD-EXCEPT"
            ]
            assert len(bare_except_findings) == 0

    def test_preserves_code_structure(self):
        """Test that refactoring preserves overall code structure."""
        code = """# This is a test file
import sys

def main():
    \"\"\"Main function.\"\"\"
    try:
        print("Hello")
    except:
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))
            assert len(plans) == 1

            refactored = plans[0].edits[0].payload

            # Check that comments and structure are preserved
            assert "# This is a test file" in refactored
            assert "import sys" in refactored
            assert "def main():" in refactored
            assert '"""Main function."""' in refactored
            assert 'print("Hello")' in refactored
            assert "except Exception:" in refactored
            assert 'if __name__ == "__main__":' in refactored
