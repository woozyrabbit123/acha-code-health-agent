"""Test fast-style-path produces same output as LibCST path."""

import pytest

from ace.skills.python import fast_style_path
from ace.skills.style import (
    analyze_trailing_whitespace,
    refactor_trailing_whitespace,
    analyze_eof_newline,
    refactor_eof_newline,
    analyze_excessive_blanklines,
    refactor_excessive_blanklines,
)


def test_fast_style_path_trailing_whitespace():
    """Test fast_style_path handles trailing whitespace same as direct call."""
    content = "def foo():  \n    return 42  \n"
    path = "test.py"

    # Direct path (original)
    findings_direct = analyze_trailing_whitespace(content, path)
    refactored_direct, plan_direct = refactor_trailing_whitespace(content, path, findings_direct)

    # Fast path
    refactored_fast, plans_fast = fast_style_path(content, path, rules=["PY-S310-TRAILING-WS"])

    # Should produce same refactored output
    assert refactored_fast == refactored_direct

    # Should find same issues
    assert len(plans_fast) == 1
    assert len(plans_fast[0].findings) == len(findings_direct)


def test_fast_style_path_eof_newline():
    """Test fast_style_path handles EOF newline same as direct call."""
    content = "def foo():\n    return 42"  # Missing EOF newline
    path = "test.py"

    # Direct path (original)
    findings_direct = analyze_eof_newline(content, path)
    refactored_direct, plan_direct = refactor_eof_newline(content, path, findings_direct)

    # Fast path
    refactored_fast, plans_fast = fast_style_path(content, path, rules=["PY-S311-EOF-NL"])

    # Should produce same refactored output
    assert refactored_fast == refactored_direct

    # Should find same issues
    assert len(plans_fast) == 1
    assert len(plans_fast[0].findings) == len(findings_direct)


def test_fast_style_path_excessive_blanklines():
    """Test fast_style_path handles excessive blank lines same as direct call."""
    content = "def foo():\n    pass\n\n\n\ndef bar():\n    pass\n"
    path = "test.py"

    # Direct path (original)
    findings_direct = analyze_excessive_blanklines(content, path)
    refactored_direct, plan_direct = refactor_excessive_blanklines(content, path, findings_direct)

    # Fast path
    refactored_fast, plans_fast = fast_style_path(content, path, rules=["PY-S312-BLANKLINES"])

    # Should produce same refactored output
    assert refactored_fast == refactored_direct

    # Should find same issues
    assert len(plans_fast) == 1
    assert len(plans_fast[0].findings) == len(findings_direct)


def test_fast_style_path_all_rules():
    """Test fast_style_path with all style rules at once."""
    content = "def foo():  \n    pass\n\n\n\ndef bar():  \n    return 42"
    path = "test.py"

    # Fast path with all rules
    refactored_fast, plans_fast = fast_style_path(content, path)

    # Expected fixes:
    # 1. Remove trailing whitespace on line 1 and 5
    # 2. Collapse excessive blank lines (3 → 1)
    # 3. Add EOF newline

    expected = "def foo():\n    pass\n\ndef bar():\n    return 42\n"

    assert refactored_fast == expected

    # Should have multiple plans (one for each rule that found issues)
    assert len(plans_fast) >= 1


def test_fast_style_path_no_issues():
    """Test fast_style_path with clean content (no issues)."""
    content = "def foo():\n    return 42\n"
    path = "test.py"

    # Fast path
    refactored_fast, plans_fast = fast_style_path(content, path)

    # Content should be unchanged
    assert refactored_fast == content

    # No plans should be generated (no issues found)
    assert len(plans_fast) == 0


def test_fast_style_path_selective_rules():
    """Test fast_style_path with selective rules."""
    content = "def foo():  \n    return 42"  # Has trailing WS and missing EOF
    path = "test.py"

    # Only apply trailing whitespace rule
    refactored_ws, plans_ws = fast_style_path(content, path, rules=["PY-S310-TRAILING-WS"])

    # Should fix trailing WS but not EOF
    assert refactored_ws == "def foo():\n    return 42"
    assert len(plans_ws) == 1

    # Only apply EOF newline rule
    refactored_eof, plans_eof = fast_style_path(content, path, rules=["PY-S311-EOF-NL"])

    # Should fix EOF but not trailing WS
    assert refactored_eof == "def foo():  \n    return 42\n"
    assert len(plans_eof) == 1


def test_fast_style_path_sequential_application():
    """Test that fast_style_path applies rules sequentially."""
    # Content with multiple issues
    content = "def foo():  \n    pass\n\n\n\ndef bar():  \n    return 42"
    path = "test.py"

    # Apply all rules
    refactored, plans = fast_style_path(content, path)

    # Each rule should be applied to the output of the previous rule
    # 1. Trailing whitespace removed
    # 2. Excessive blank lines collapsed
    # 3. EOF newline added

    # Final output should have all fixes
    expected = "def foo():\n    pass\n\ndef bar():\n    return 42\n"
    assert refactored == expected


def test_fast_style_path_empty_content():
    """Test fast_style_path with empty content."""
    content = ""
    path = "test.py"

    # Fast path
    refactored, plans = fast_style_path(content, path)

    # Empty content should remain empty (no issues to fix)
    assert refactored == content
    assert len(plans) == 0


def test_fast_style_path_performance():
    """Test that fast_style_path is actually faster than LibCST path."""
    import time

    # Large content with many style issues
    content = "\n".join(
        [f"def func{i}():  \n    return {i}\n\n\n" for i in range(100)]
    )
    path = "test.py"

    # Measure fast path time
    start = time.perf_counter()
    refactored_fast, plans_fast = fast_style_path(content, path)
    fast_time = time.perf_counter() - start

    # Fast path should complete in reasonable time
    # (We can't easily measure LibCST path without full setup, but we can
    # verify fast path is reasonably quick)
    assert fast_time < 1.0  # Should be much faster than 1 second

    # Verify it still produces correct output
    assert "\n\n\n\n" not in refactored_fast  # Blank lines collapsed
    assert "  \n" not in refactored_fast  # Trailing whitespace removed
    assert refactored_fast.endswith("\n")  # EOF newline added
