"""Tests for PY-I101-IMPORT-SORT rule."""

import tempfile
from pathlib import Path

from ace.kernel import run_analyze, run_apply, run_refactor
from ace.skills.python import validate_python_syntax


class TestImportSort:
    """Test PY-I101-IMPORT-SORT rule."""

    def test_analyze_detects_unsorted_imports(self):
        """Test that unsorted imports are detected."""
        code = """import sys
import os
import argparse
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            findings = run_analyze(Path(tmpdir))

            # Should find unsorted imports
            import_findings = [f for f in findings if f.rule == "PY-I101-IMPORT-SORT"]
            assert len(import_findings) == 1
            assert import_findings[0].severity.value == "low"
            assert "imports not sorted" in import_findings[0].message

    def test_refactor_sorts_imports(self):
        """Test that imports are sorted alphabetically."""
        code = """import sys
import os
import argparse

def main():
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

            # Check that imports are now sorted
            lines = edit.payload.splitlines()
            import_lines = [line for line in lines if line.startswith("import ")]

            # Should be sorted: argparse, os, sys
            assert import_lines[0] == "import argparse"
            assert import_lines[1] == "import os"
            assert import_lines[2] == "import sys"

            # Verify valid syntax
            assert validate_python_syntax(edit.payload)

    def test_apply_sorts_imports(self):
        """Test that applying changes sorts the imports."""
        code = """import sys
import json
import os

def foo():
    return os.getcwd()
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            # Apply the refactoring
            result = run_apply(Path(tmpdir), dry_run=False)
            assert result == 0

            # Read the modified file
            modified_content = test_file.read_text()
            lines = modified_content.splitlines()
            import_lines = [line for line in lines if line.startswith("import ")]

            # Should be sorted: json, os, sys
            assert import_lines == ["import json", "import os", "import sys"]
            assert validate_python_syntax(modified_content)

    def test_idempotency(self):
        """Test that applying twice produces same result."""
        code = """import sys
import os
import argparse
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            # Apply once
            result1 = run_apply(Path(tmpdir), dry_run=False)
            assert result1 == 0

            first_content = test_file.read_text()

            # Apply again
            result2 = run_apply(Path(tmpdir), dry_run=False)
            assert result2 == 0

            second_content = test_file.read_text()

            # Content should be the same
            assert first_content == second_content

    def test_no_false_positives(self):
        """Test that already sorted imports are not flagged."""
        code = """import argparse
import os
import sys

def main():
    pass
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            findings = run_analyze(Path(tmpdir))

            # Should not find any unsorted imports
            import_findings = [f for f in findings if f.rule == "PY-I101-IMPORT-SORT"]
            assert len(import_findings) == 0

    def test_preserves_from_imports(self):
        """Test that from imports are also sorted correctly."""
        code = """from pathlib import Path
from typing import List
import sys
import os

def foo():
    pass
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            if plans:
                edit = plans[0].edits[0]
                refactored = edit.payload

                # Verify valid syntax
                assert validate_python_syntax(refactored)

                # Check that imports are sorted
                lines = refactored.splitlines()
                import_section = []
                for line in lines:
                    if line.startswith("import ") or line.startswith("from "):
                        import_section.append(line)
                    elif import_section:
                        break

                # Should be sorted alphabetically
                assert import_section == sorted(import_section)

    def test_preserves_code_after_imports(self):
        """Test that code after imports is preserved."""
        code = """import sys
import os

# This is a comment
def main():
    \"\"\"Main function.\"\"\"
    print("Hello, World!")

if __name__ == "__main__":
    main()
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))
            assert len(plans) == 1

            refactored = plans[0].edits[0].payload

            # Check that code structure is preserved
            assert "# This is a comment" in refactored
            assert "def main():" in refactored
            assert '"""Main function."""' in refactored
            assert 'print("Hello, World!")' in refactored
            assert 'if __name__ == "__main__":' in refactored

    def test_determinism(self):
        """Test that sorting is deterministic."""
        code = """import sys
import os
import json
import argparse
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            # Run refactor twice
            plans1 = run_refactor(Path(tmpdir))
            plans2 = run_refactor(Path(tmpdir))

            # Results should be identical
            assert len(plans1) == len(plans2)
            if plans1:
                assert plans1[0].edits[0].payload == plans2[0].edits[0].payload
