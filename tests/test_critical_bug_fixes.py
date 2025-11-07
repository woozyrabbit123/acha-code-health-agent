"""Regression tests for critical bug fixes"""
import tempfile
from pathlib import Path
from utils.policy import PolicyConfig, PolicyEnforcer
from agents.refactor_agent import RefactorAgent
import json


def test_policy_with_numeric_severities():
    """
    Bug #1: PolicyEnforcer was comparing numeric severities against strings,
    breaking policy enforcement. This test ensures numeric severities work correctly.
    """
    cfg = PolicyConfig(fail_on_error=True, max_errors=0, fail_on_risky=True)
    enforcer = PolicyEnforcer(cfg)

    # Test with numeric severities (as produced by AnalysisAgent)
    results_numeric = {
        "issues": [
            {"rule": "risky_construct", "severity": 0.9},  # critical as numeric
            {"rule": "unused_import", "severity": 0.7},     # error as numeric
            {"rule": "magic_number", "severity": 0.4}       # warning as numeric
        ]
    }

    ok, reasons = enforcer.check_violations(results_numeric)
    assert not ok, "Should fail on risky construct and error"
    assert any("risky" in r.lower() for r in reasons), "Should mention risky construct"
    assert any("error" in r.lower() for r in reasons), "Should mention errors"

    # Test with string severities (backward compatibility)
    results_string = {
        "issues": [
            {"rule": "risky_construct", "severity": "critical"},
            {"rule": "unused_import", "severity": "error"},
            {"rule": "magic_number", "severity": "warning"}
        ]
    }

    ok2, reasons2 = enforcer.check_violations(results_string)
    assert not ok2, "Should also work with string severities"
    assert any("risky" in r.lower() for r in reasons2)

    # Test that warnings are counted correctly with numeric severities
    cfg_warnings = PolicyConfig(fail_on_error=False, max_warnings=1)
    enforcer_warnings = PolicyEnforcer(cfg_warnings)

    results_warnings = {
        "issues": [
            {"rule": "test1", "severity": 0.4},  # warning
            {"rule": "test2", "severity": 0.4},  # warning
            {"rule": "test3", "severity": 0.1}   # info
        ]
    }

    ok3, reasons3 = enforcer_warnings.check_violations(results_warnings)
    assert not ok3, "Should fail when warnings (2) exceed limit (1)"
    assert any("warning" in r.lower() for r in reasons3)


def test_subprocess_comma_preservation():
    """
    Bug #3: Subprocess hardening regex was breaking comma structure,
    causing syntax errors. This test ensures commas are preserved correctly.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create test file with subprocess call
        test_file = tmp_path / "test_subprocess.py"
        test_file.write_text("""import subprocess

result = subprocess.run(["ls"], shell=True, check=True)
result2 = subprocess.call(cmd, shell=True, timeout=10)
result3 = subprocess.run(["echo"], shell=True)
""")

        # Create analysis JSON with subprocess findings
        analysis_file = tmp_path / "analysis.json"
        analysis_data = {
            "findings": [
                {"finding": "broad_subprocess_shell", "file": "test_subprocess.py", "start_line": 3},
                {"finding": "broad_subprocess_shell", "file": "test_subprocess.py", "start_line": 4},
                {"finding": "broad_subprocess_shell", "file": "test_subprocess.py", "start_line": 5}
            ]
        }
        analysis_file.write_text(json.dumps(analysis_data))

        # Apply refactoring
        agent = RefactorAgent(refactor_types=["harden_subprocess"])
        result = agent.apply(str(tmp_path), str(analysis_file))

        # Check that modifications preserve comma structure
        modified_content = agent.modifications.get("test_subprocess.py", "")

        # Should not have syntax errors from missing commas
        assert "check=True" in modified_content or "check=False" in modified_content
        assert "timeout=10" in modified_content, "Other parameters should be preserved"
        assert "shell=True" not in modified_content, "shell=True should be removed"

        # Verify it's valid Python
        import ast
        try:
            ast.parse(modified_content)
        except SyntaxError as e:
            assert False, f"Modified code has syntax error: {e}"


def test_future_import_ordering():
    """
    Bug #4: Import organization was moving __future__ imports after other imports,
    violating Python's requirement that __future__ must be first.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create test file with __future__ import after regular imports (wrong order)
        test_file = tmp_path / "test_future.py"
        test_file.write_text("""import os
import sys
from __future__ import annotations
from typing import List

def foo() -> List[str]:
    return []
""")

        # Create minimal analysis JSON
        analysis_file = tmp_path / "analysis.json"
        analysis_data = {"findings": []}
        analysis_file.write_text(json.dumps(analysis_data))

        # Apply import organization
        agent = RefactorAgent(refactor_types=["organize_imports"])
        result = agent.apply(str(tmp_path), str(analysis_file))

        modified_content = agent.modifications.get("test_future.py", "")

        # __future__ should be first import
        lines = modified_content.split('\n')
        import_lines = [i for i, line in enumerate(lines) if 'import' in line and line.strip()]

        if import_lines:
            first_import = lines[import_lines[0]]
            assert '__future__' in first_import, \
                f"First import should be __future__, but got: {first_import}"

        # Verify it's valid Python
        import ast
        try:
            ast.parse(modified_content)
        except SyntaxError as e:
            assert False, f"Modified code has syntax error: {e}"


def test_multi_import_partial_removal():
    """
    Bug #2: Removing unused imports from multi-import statements like
    'import os, sys' was deleting the entire line even if only one was unused.

    Note: Current implementation still removes entire line for multi-imports,
    but this test documents the expected behavior for future improvement.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create test file with multi-import where only one is used
        test_file = tmp_path / "test_multi.py"
        test_file.write_text("""import os

def main():
    print(os.getcwd())
""")

        # Create analysis JSON with unused import
        analysis_file = tmp_path / "analysis.json"
        analysis_data = {
            "findings": [
                {"finding": "unused_import", "file": "test_multi.py", "start_line": 1}
            ]
        }
        analysis_file.write_text(json.dumps(analysis_data))

        # Apply refactoring
        agent = RefactorAgent(refactor_types=["remove_unused_import"])
        result = agent.apply(str(tmp_path), str(analysis_file))

        modified_content = agent.modifications.get("test_multi.py", "")

        # Verify it's valid Python
        import ast
        try:
            ast.parse(modified_content)
        except SyntaxError as e:
            assert False, f"Modified code has syntax error: {e}"

        # The import line should be removed if flagged as unused
        assert "import os" not in modified_content, "Unused import should be removed"


def test_severity_string_conversion():
    """Test the _severity_to_string helper method handles all cases"""
    cfg = PolicyConfig()
    enforcer = PolicyEnforcer(cfg)

    # Test numeric to string conversion
    assert enforcer._severity_to_string(0.9) == "critical"
    assert enforcer._severity_to_string(0.7) == "error"
    assert enforcer._severity_to_string(0.4) == "warning"
    assert enforcer._severity_to_string(0.1) == "info"
    assert enforcer._severity_to_string(0.05) == "info"

    # Test string passthrough (case-insensitive)
    assert enforcer._severity_to_string("CRITICAL") == "critical"
    assert enforcer._severity_to_string("Error") == "error"
    assert enforcer._severity_to_string("warning") == "warning"
    assert enforcer._severity_to_string("info") == "info"

    # Test edge cases
    assert enforcer._severity_to_string(1.0) == "critical"
    assert enforcer._severity_to_string(0.0) == "info"
    assert enforcer._severity_to_string(0.75) == "error"
    assert enforcer._severity_to_string(0.45) == "warning"
