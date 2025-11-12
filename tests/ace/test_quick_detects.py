"""Tests for ACE quick detect rules."""

from ace.skills.quick_detects import (
    analyze_assert_in_nontest,
    analyze_print_in_src,
    analyze_eval_exec,
)


def test_assert_in_nontest_detected():
    """Test detection of assert in non-test code."""
    code = "def foo():\n    assert x > 0\n"
    findings = analyze_assert_in_nontest(code, "src/main.py")

    assert len(findings) == 1
    assert findings[0].rule == "PY-Q201-ASSERT-IN-NONTEST"


def test_assert_in_test_ignored():
    """Test that assert in test files is not flagged."""
    code = "def test_foo():\n    assert x > 0\n"
    findings = analyze_assert_in_nontest(code, "tests/test_main.py")

    assert len(findings) == 0


def test_print_in_src_detected():
    """Test detection of print in src code."""
    code = "def foo():\n    print('hello')\n"
    findings = analyze_print_in_src(code, "/project/src/main.py")

    assert len(findings) == 1
    assert findings[0].rule == "PY-Q202-PRINT-IN-SRC"


def test_print_outside_src_ignored():
    """Test that print outside src is not flagged."""
    code = "def foo():\n    print('hello')\n"
    findings = analyze_print_in_src(code, "scripts/build.py")

    assert len(findings) == 0


def test_eval_detected():
    """Test detection of eval()."""
    code = "result = eval(user_input)\n"
    findings = analyze_eval_exec(code, "main.py")

    assert len(findings) == 1
    assert findings[0].rule == "PY-Q203-EVAL-EXEC"
    assert findings[0].severity == "high"
    assert "eval" in findings[0].message


def test_exec_detected():
    """Test detection of exec()."""
    code = "exec(user_code)\n"
    findings = analyze_eval_exec(code, "main.py")

    assert len(findings) == 1
    assert findings[0].rule == "PY-Q203-EVAL-EXEC"
    assert "exec" in findings[0].message


def test_eval_exec_multiple():
    """Test detection of multiple eval/exec calls."""
    code = "x = eval(a)\nexec(b)\ny = eval(c)\n"
    findings = analyze_eval_exec(code, "main.py")

    assert len(findings) == 3
