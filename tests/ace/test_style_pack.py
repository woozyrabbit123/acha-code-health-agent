"""Tests for ACE style rules."""

from ace.skills.style import (
    analyze_trailing_whitespace,
    analyze_eof_newline,
    analyze_excessive_blanklines,
    refactor_trailing_whitespace,
    refactor_eof_newline,
    refactor_excessive_blanklines,
)


def test_trailing_whitespace_detection():
    """Test detection of trailing whitespace."""
    code = "x = 1  \ny = 2\nz = 3  \n"
    findings = analyze_trailing_whitespace(code, "test.py")

    assert len(findings) == 2
    assert findings[0].rule == "PY-S310-TRAILING-WS"
    assert findings[0].line == 1
    assert findings[1].line == 3


def test_trailing_whitespace_refactor():
    """Test removal of trailing whitespace."""
    code = "x = 1  \ny = 2\nz = 3  \n"
    fixed, plan = refactor_trailing_whitespace(code, "test.py", [])

    assert fixed == "x = 1\ny = 2\nz = 3\n"
    assert len(plan.edits) > 0


def test_trailing_whitespace_idempotent():
    """Test that refactoring is idempotent."""
    code = "x = 1  \ny = 2\n"
    fixed1, _ = refactor_trailing_whitespace(code, "test.py", [])
    fixed2, plan2 = refactor_trailing_whitespace(fixed1, "test.py", [])

    assert fixed1 == fixed2
    assert len(plan2.edits) == 0


def test_eof_newline_missing():
    """Test detection of missing EOF newline."""
    code = "x = 1"
    findings = analyze_eof_newline(code, "test.py")

    assert len(findings) == 1
    assert findings[0].rule == "PY-S311-EOF-NL"


def test_eof_newline_refactor():
    """Test adding EOF newline."""
    code = "x = 1"
    fixed, plan = refactor_eof_newline(code, "test.py", [])

    assert fixed == "x = 1\n"
    assert len(plan.edits) > 0


def test_eof_newline_multiple():
    """Test detection of multiple EOF newlines."""
    code = "x = 1\n\n"
    findings = analyze_eof_newline(code, "test.py")

    assert len(findings) == 1


def test_excessive_blanklines_detection():
    """Test detection of excessive blank lines."""
    code = "x = 1\n\n\n\ny = 2\n"
    findings = analyze_excessive_blanklines(code, "test.py")

    assert len(findings) == 1
    assert findings[0].rule == "PY-S312-BLANKLINES"


def test_excessive_blanklines_refactor():
    """Test collapsing excessive blank lines."""
    code = "x = 1\n\n\n\ny = 2\n"
    fixed, plan = refactor_excessive_blanklines(code, "test.py", [])

    assert fixed.count("\n\n\n") == 0
    assert len(plan.edits) > 0
