"""Tests for patch guard."""

import pytest

from ace.guard import (
    guard_python_edit,
    verify_ast_equivalence,
    verify_cst_roundtrip,
    verify_python_parse,
    format_guard_error,
    get_guard_summary,
)


class TestVerifyPythonParse:
    """Tests for Python parse verification."""

    def test_valid_python(self):
        """Test valid Python code."""
        success, errors = verify_python_parse("print('hello')")
        assert success
        assert len(errors) == 0

    def test_syntax_error(self):
        """Test syntax error detection."""
        success, errors = verify_python_parse("print('hello'")
        assert not success
        assert len(errors) > 0


class TestVerifyASTEquivalence:
    """Tests for AST equivalence checking."""

    def test_equivalent_code(self):
        """Test equivalent code (different whitespace)."""
        before = "x = 1"
        after = "x=1"  # Different whitespace
        equiv, errors = verify_ast_equivalence(before, after)
        assert equiv

    def test_different_code(self):
        """Test non-equivalent code."""
        before = "x = 1"
        after = "x = 2"
        equiv, errors = verify_ast_equivalence(before, after)
        assert not equiv


class TestVerifyCSTRoundtrip:
    """Tests for CST roundtrip verification."""

    def test_valid_roundtrip(self):
        """Test valid CST roundtrip."""
        code = "print('hello')\n"
        success, errors = verify_cst_roundtrip(code)
        assert success

    def test_complex_code(self):
        """Test complex code roundtrip."""
        code = """
def foo(x: int) -> int:
    '''Docstring'''
    return x + 1
"""
        success, errors = verify_cst_roundtrip(code)
        assert success


class TestGuardPythonEdit:
    """Tests for Python edit guarding."""

    def test_safe_edit(self):
        """Test safe edit passes guard."""
        before = "x = 1\n"
        after = "x=1\n"  # Same semantics, different formatting
        result = guard_python_edit("test.py", before, after, strict=True)
        assert result.passed

    def test_semantic_change(self):
        """Test semantic change fails strict guard."""
        before = "x = 1\n"
        after = "x = 2\n"
        result = guard_python_edit("test.py", before, after, strict=True)
        assert not result.passed
        assert result.guard_type == "ast_equiv"

    def test_syntax_error(self):
        """Test syntax error fails guard."""
        before = "x = 1\n"
        after = "x = \n"  # Syntax error
        result = guard_python_edit("test.py", before, after)
        assert not result.passed
        assert result.guard_type == "parse"

    def test_non_strict_allows_semantic_change(self):
        """Test non-strict mode allows semantic changes."""
        before = "x = 1\n"
        after = "x = 2\n"
        result = guard_python_edit("test.py", before, after, strict=False)
        # Should pass (only checks parse + CST roundtrip)
        assert result.passed or result.guard_type == "cst_apply"


class TestFormatGuardError:
    """Tests for guard error formatting."""

    def test_format_error(self):
        """Test error formatting."""
        result = guard_python_edit("test.py", "x=1", "x=", strict=False)
        error_msg = format_guard_error(result)
        assert "PATCH GUARD FAILED" in error_msg
        assert "test.py" in error_msg


class TestGetGuardSummary:
    """Tests for guard summary."""

    def test_summary(self):
        """Test summary generation."""
        result1 = guard_python_edit("test.py", "x=1", "x=1", strict=True)
        result2 = guard_python_edit("test.py", "x=1", "x=", strict=False)

        summary = get_guard_summary([result1, result2])
        assert summary["total"] == 2
        assert summary["passed"] >= 1
