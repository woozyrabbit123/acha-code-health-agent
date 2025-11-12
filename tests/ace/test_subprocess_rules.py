"""Tests for subprocess hardening rules."""

import tempfile
from pathlib import Path

from ace.skills.python import (
    analyze_subprocess_check,
    analyze_subprocess_shell,
    analyze_subprocess_string_cmd,
    refactor_subprocess_check,
)


def test_subprocess_check_missing():
    """Test detection of subprocess.run() without check parameter."""
    code = """
import subprocess

def run_command():
    result = subprocess.run(["echo", "hello"])
    return result
"""
    findings = analyze_subprocess_check(code, "test.py")
    assert len(findings) == 1
    assert findings[0].rule == "PY-S201-SUBPROCESS-CHECK"
    assert findings[0].severity == "medium"
    assert "check=" in findings[0].message


def test_subprocess_check_present():
    """Test that subprocess.run() with check parameter is not flagged."""
    code = """
import subprocess

def run_command():
    result = subprocess.run(["echo", "hello"], check=True)
    return result
"""
    findings = analyze_subprocess_check(code, "test.py")
    assert len(findings) == 0


def test_subprocess_check_multiple():
    """Test detection of multiple subprocess.run() calls."""
    code = """
import subprocess

def cmd1():
    subprocess.run(["ls"])

def cmd2():
    subprocess.run(["pwd"], check=True)  # OK

def cmd3():
    subprocess.run(["date"])  # Missing check
"""
    findings = analyze_subprocess_check(code, "test.py")
    assert len(findings) == 2
    assert all(f.rule == "PY-S201-SUBPROCESS-CHECK" for f in findings)


def test_subprocess_check_refactor():
    """Test refactoring adds check=True."""
    code = """
import subprocess

result = subprocess.run(["echo", "hello"])
"""
    findings = analyze_subprocess_check(code, "test.py")
    assert len(findings) == 1

    refactored, plan = refactor_subprocess_check(code, "test.py", findings)

    # Check that check=True was added
    assert "check=True" in refactored
    assert refactored.strip().endswith('run(["echo", "hello"], check=True)')

    # Verify plan structure
    assert plan.findings == findings
    assert len(plan.edits) == 1
    assert plan.edits[0].op == "replace"


def test_subprocess_check_refactor_idempotent():
    """Test that refactoring is idempotent."""
    code = """
import subprocess

result = subprocess.run(["echo", "hello"])
"""
    findings = analyze_subprocess_check(code, "test.py")
    refactored1, _ = refactor_subprocess_check(code, "test.py", findings)

    # Second refactor should not change anything
    findings2 = analyze_subprocess_check(refactored1, "test.py")
    assert len(findings2) == 0


def test_subprocess_check_preserves_other_args():
    """Test that refactoring preserves other arguments."""
    code = """
import subprocess

result = subprocess.run(["echo", "hello"], capture_output=True, text=True)
"""
    findings = analyze_subprocess_check(code, "test.py")
    refactored, _ = refactor_subprocess_check(code, "test.py", findings)

    assert "capture_output=True" in refactored
    assert "text=True" in refactored
    assert "check=True" in refactored


def test_subprocess_shell_detection():
    """Test detection of shell=True in subprocess calls."""
    code = """
import subprocess

def dangerous():
    subprocess.run("echo hello", shell=True)
"""
    findings = analyze_subprocess_shell(code, "test.py")
    assert len(findings) == 1
    assert findings[0].rule == "PY-S202-SUBPROCESS-SHELL"
    assert findings[0].severity == "high"
    assert "shell=True" in findings[0].message


def test_subprocess_shell_false_ok():
    """Test that shell=False is not flagged."""
    code = """
import subprocess

def safe():
    subprocess.run(["echo", "hello"], shell=False)
"""
    findings = analyze_subprocess_shell(code, "test.py")
    assert len(findings) == 0


def test_subprocess_shell_no_shell_arg():
    """Test that subprocess calls without shell arg are not flagged."""
    code = """
import subprocess

def safe():
    subprocess.run(["echo", "hello"])
"""
    findings = analyze_subprocess_shell(code, "test.py")
    assert len(findings) == 0


def test_subprocess_shell_various_functions():
    """Test detection across different subprocess functions."""
    code = """
import subprocess

subprocess.run("cmd", shell=True)
subprocess.call("cmd", shell=True)
subprocess.check_call("cmd", shell=True)
subprocess.check_output("cmd", shell=True)
subprocess.Popen("cmd", shell=True)
"""
    findings = analyze_subprocess_shell(code, "test.py")
    assert len(findings) == 5
    assert all(f.rule == "PY-S202-SUBPROCESS-SHELL" for f in findings)


def test_subprocess_string_cmd_detection():
    """Test detection of string commands in subprocess."""
    code = """
import subprocess

def bad():
    subprocess.run("echo hello")
"""
    findings = analyze_subprocess_string_cmd(code, "test.py")
    assert len(findings) == 1
    assert findings[0].rule == "PY-S203-SUBPROCESS-STRING-CMD"
    assert findings[0].severity == "medium"


def test_subprocess_string_cmd_list_ok():
    """Test that list commands are not flagged."""
    code = """
import subprocess

def good():
    subprocess.run(["echo", "hello"])
"""
    findings = analyze_subprocess_string_cmd(code, "test.py")
    assert len(findings) == 0


def test_subprocess_string_cmd_various_functions():
    """Test detection across different subprocess functions."""
    code = """
import subprocess

subprocess.run("cmd")
subprocess.call("cmd")
subprocess.check_call("cmd")
subprocess.check_output("cmd")
subprocess.Popen("cmd")
"""
    findings = analyze_subprocess_string_cmd(code, "test.py")
    assert len(findings) == 5
    assert all(f.rule == "PY-S203-SUBPROCESS-STRING-CMD" for f in findings)


def test_subprocess_combined_issues():
    """Test file with multiple different subprocess issues."""
    code = """
import subprocess

def issue1():
    subprocess.run(["ls"])  # Missing check

def issue2():
    subprocess.run("ls", shell=True)  # shell=True + string cmd

def issue3():
    subprocess.run("pwd")  # String cmd + missing check

def ok():
    subprocess.run(["pwd"], check=True)  # OK
"""
    findings_check = analyze_subprocess_check(code, "test.py")
    findings_shell = analyze_subprocess_shell(code, "test.py")
    findings_string = analyze_subprocess_string_cmd(code, "test.py")

    # issue1: missing check
    assert len([f for f in findings_check if f.line == 5]) == 1

    # issue2: shell=True and string cmd
    assert len([f for f in findings_shell if f.line == 8]) == 1
    assert len([f for f in findings_string if f.line == 8]) == 1

    # issue3: string cmd and missing check (check rule doesn't flag strings)
    assert len([f for f in findings_string if f.line == 11]) == 1


def test_subprocess_rules_parse_after_edit():
    """Test that refactored code is valid Python."""
    code = """
import subprocess

def deploy():
    subprocess.run(["git", "push"])
    subprocess.run(["npm", "install"])
"""
    findings = analyze_subprocess_check(code, "test.py")
    refactored, _ = refactor_subprocess_check(code, "test.py", findings)

    # Verify it can be parsed again
    import ast
    ast.parse(refactored)  # Should not raise


def test_subprocess_empty_file():
    """Test handling of empty file."""
    code = ""
    findings = analyze_subprocess_check(code, "test.py")
    assert len(findings) == 0


def test_subprocess_no_subprocess_import():
    """Test file without subprocess usage."""
    code = """
import os

def main():
    print("Hello")
"""
    findings = analyze_subprocess_check(code, "test.py")
    assert len(findings) == 0


def test_subprocess_check_integration():
    """Integration test with actual file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "script.py"
        test_file.write_text(
            """
import subprocess

def deploy():
    subprocess.run(["git", "push"])
    subprocess.run(["npm", "build"], check=True)
""",
            encoding="utf-8",
        )

        content = test_file.read_text(encoding="utf-8")
        findings = analyze_subprocess_check(content, str(test_file))

        # Only first call should be flagged
        assert len(findings) == 1
        assert findings[0].line == 5

        # Refactor
        refactored, _ = refactor_subprocess_check(content, str(test_file), findings)

        # Write back and verify
        test_file.write_text(refactored, encoding="utf-8")
        new_content = test_file.read_text(encoding="utf-8")

        # Should have no more findings
        new_findings = analyze_subprocess_check(new_content, str(test_file))
        assert len(new_findings) == 0


def test_subprocess_refactor_no_findings():
    """Test refactoring with empty findings list."""
    code = """
import subprocess

subprocess.run(["echo", "hello"], check=True)
"""
    refactored, plan = refactor_subprocess_check(code, "test.py", [])

    # Should return original code unchanged
    assert refactored == code
    assert len(plan.findings) == 0
    assert len(plan.edits) == 0


def test_subprocess_invalid_python():
    """Test handling of invalid Python syntax."""
    code = "this is not valid python !!!"

    # Should return empty list, not crash
    findings = analyze_subprocess_check(code, "test.py")
    assert len(findings) == 0

    findings = analyze_subprocess_shell(code, "test.py")
    assert len(findings) == 0

    findings = analyze_subprocess_string_cmd(code, "test.py")
    assert len(findings) == 0
