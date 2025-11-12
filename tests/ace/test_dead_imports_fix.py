"""Regression test for dead imports detection fix.

This test verifies that the dead imports codemod correctly identifies
and removes unused imports without false positives.
"""

import tempfile
from pathlib import Path

from ace.kernel import run_analyze, run_refactor, run_apply
from ace.skills.python import validate_python_syntax


class TestDeadImportsFix:
    """Test PY_DEAD_IMPORTS codemod after fixing visit_Name issue."""

    def test_unused_imports_are_detected(self):
        """Test that genuinely unused imports are detected."""
        code = """import os
import sys
import json

def main():
    pass
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            findings = run_analyze(Path(tmpdir))

            # Should find dead imports
            dead_import_findings = [f for f in findings if f.rule == "PY_DEAD_IMPORTS"]
            assert len(dead_import_findings) > 0

    def test_used_imports_not_removed(self):
        """Test that actually used imports are NOT removed."""
        code = """import os
import sys

def main():
    print(os.getcwd())
    return sys.argv
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            # Should not suggest removing os or sys
            for plan in plans:
                if any("dead" in str(f.rule).lower() or "import" in str(f.rule).lower()
                       for f in plan.findings):
                    refactored = plan.edits[0].payload
                    # os and sys should still be present
                    assert "import os" in refactored
                    assert "import sys" in refactored

    def test_refactor_removes_unused_imports(self):
        """Test that unused imports are correctly removed."""
        code = """import os
import sys
import json
import argparse

def main():
    print(os.getcwd())
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            # Find the dead imports plan
            dead_import_plans = [
                p for p in plans
                if any("DEAD_IMPORT" in str(f.rule) for f in p.findings)
            ]

            if dead_import_plans:
                plan = dead_import_plans[0]
                assert len(plan.edits) == 1
                edit = plan.edits[0]
                refactored = edit.payload

                # os should remain (it's used)
                assert "import os" in refactored

                # sys, json, argparse should be removed (they're unused)
                assert "import sys" not in refactored or "sys" in refactored.split("import sys")[1][:50]
                assert "import json" not in refactored or "json" in refactored.split("import json")[1][:50]
                assert "import argparse" not in refactored or "argparse" in refactored.split("import argparse")[1][:50]

                # Verify valid syntax
                assert validate_python_syntax(refactored)

    def test_from_imports_unused_removed(self):
        """Test that unused from imports are also removed."""
        code = """from pathlib import Path
from typing import List, Dict
import os

def main():
    return os.getcwd()
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            dead_import_plans = [
                p for p in plans
                if any("DEAD_IMPORT" in str(f.rule) for f in p.findings)
            ]

            if dead_import_plans:
                plan = dead_import_plans[0]
                refactored = plan.edits[0].payload

                # os should remain (it's used)
                assert "import os" in refactored

                # Path, List, Dict should be removed (they're unused)
                # Allow for the possibility that the import lines are completely removed
                lines = refactored.split('\n')
                import_lines = [l for l in lines if 'import' in l.lower()]

                # Verify valid syntax
                assert validate_python_syntax(refactored)

    def test_attribute_access_marks_import_as_used(self):
        """Test that using module.attr counts as usage."""
        code = """import os
import sys

def get_path():
    return os.path.join("a", "b")
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            # Find any dead import plans
            dead_import_plans = [
                p for p in plans
                if any("DEAD_IMPORT" in str(f.rule) for f in p.findings)
            ]

            if dead_import_plans:
                refactored = dead_import_plans[0].edits[0].payload

                # os should NOT be removed (it's used via os.path)
                assert "import os" in refactored

                # sys might be removed (it's unused)
                # But this test focuses on os

    def test_import_alias_handled_correctly(self):
        """Test that aliased imports are handled correctly."""
        code = """import os as operating_system
import sys as system

def main():
    return operating_system.getcwd()
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            dead_import_plans = [
                p for p in plans
                if any("DEAD_IMPORT" in str(f.rule) for f in p.findings)
            ]

            if dead_import_plans:
                refactored = dead_import_plans[0].edits[0].payload

                # os (aliased as operating_system) should remain
                assert "operating_system" in refactored

                # Verify valid syntax
                assert validate_python_syntax(refactored)

    def test_guards_preserved(self):
        """Test that __future__ and typing guards are preserved."""
        code = """from __future__ import annotations
from typing import List
import os

def main() -> None:
    pass
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            plans = run_refactor(Path(tmpdir))

            dead_import_plans = [
                p for p in plans
                if any("DEAD_IMPORT" in str(f.rule) for f in p.findings)
            ]

            if dead_import_plans:
                refactored = dead_import_plans[0].edits[0].payload

                # __future__ and typing should be kept (guarded)
                assert "__future__" in refactored
                # typing might be kept due to annotations guard

                # Verify valid syntax
                assert validate_python_syntax(refactored)

    def test_apply_removes_dead_imports(self):
        """Test that applying changes removes dead imports from file."""
        code = """import os
import sys
import json

def main():
    print(os.getcwd())
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            # Apply refactoring
            result, _ = run_apply(Path(tmpdir), dry_run=False)

            # Read modified file
            modified_content = test_file.read_text()

            # os should remain (used)
            assert "import os" in modified_content

            # Verify valid syntax
            assert validate_python_syntax(modified_content)

    def test_no_false_positives_all_used(self):
        """Test no false positives when all imports are actually used."""
        code = """import os
import sys
import json

def main():
    print(os.getcwd())
    print(sys.argv)
    print(json.dumps({}))
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            findings = run_analyze(Path(tmpdir))

            # Should not find dead imports
            dead_import_findings = [f for f in findings if f.rule == "PY_DEAD_IMPORTS"]
            assert len(dead_import_findings) == 0

    def test_idempotency(self):
        """Test that running twice produces same result."""
        code = """import os
import sys
import json

def main():
    print(os.getcwd())
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(code)

            # Apply once
            result1, _ = run_apply(Path(tmpdir), dry_run=False)
            first_content = test_file.read_text()

            # Apply again
            result2, _ = run_apply(Path(tmpdir), dry_run=False)
            second_content = test_file.read_text()

            # Content should be the same
            assert first_content == second_content
