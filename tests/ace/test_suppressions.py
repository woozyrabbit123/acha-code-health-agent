"""Tests for suppression directive parsing."""

from ace.suppressions import (
    Suppression,
    SuppressionScope,
    filter_findings_by_suppressions,
    is_rule_suppressed,
    parse_suppression_directive,
    parse_suppressions,
)
from ace.uir import Severity, UnifiedIssue


class TestParseDirective:
    """Test parsing individual suppression directives."""

    def test_parse_disable_block(self):
        """Test parsing block disable directive."""
        result = parse_suppression_directive("# ace:disable PY-E201", 10)

        assert result is not None
        assert result.line == 10
        assert result.scope == SuppressionScope.BLOCK
        assert result.rule_ids == {"PY-E201"}
        assert result.enabled is False

    def test_parse_disable_multiple_rules(self):
        """Test parsing disable with multiple rules."""
        result = parse_suppression_directive("# ace:disable PY-E201,PY-I101", 5)

        assert result is not None
        assert result.rule_ids == {"PY-E201", "PY-I101"}

    def test_parse_disable_all_rules(self):
        """Test parsing disable without rule IDs (all rules)."""
        result = parse_suppression_directive("# ace:disable", 1)

        assert result is not None
        assert result.rule_ids == set()  # Empty = all rules
        assert result.enabled is False

    def test_parse_disable_line(self):
        """Test parsing line-level disable."""
        result = parse_suppression_directive("x = 1  # ace:disable-line PY-E201", 7)

        assert result is not None
        assert result.scope == SuppressionScope.LINE
        assert result.line == 7

    def test_parse_disable_next_line(self):
        """Test parsing next-line disable."""
        result = parse_suppression_directive("# ace:disable-next-line PY-E201", 3)

        assert result is not None
        assert result.scope == SuppressionScope.NEXT_LINE
        assert result.line == 3

    def test_parse_enable_block(self):
        """Test parsing enable directive."""
        result = parse_suppression_directive("# ace:enable PY-E201", 20)

        assert result is not None
        assert result.scope == SuppressionScope.BLOCK
        assert result.enabled is True

    def test_parse_markdown_comment(self):
        """Test parsing from Markdown HTML comment."""
        result = parse_suppression_directive(
            "<!-- ace:disable MD-L001 -->", 5
        )

        assert result is not None
        assert result.rule_ids == {"MD-L001"}

    def test_parse_case_insensitive(self):
        """Test that directives are case-insensitive."""
        result = parse_suppression_directive("# ACE:DISABLE py-e201", 1)

        assert result is not None
        assert result.rule_ids == {"py-e201"}

    def test_parse_no_directive(self):
        """Test parsing line without directive."""
        result = parse_suppression_directive("regular code line", 1)

        assert result is None

    def test_parse_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        result = parse_suppression_directive(
            "#   ace:disable   PY-E201  ,  PY-I101  ", 1
        )

        assert result is not None
        assert result.rule_ids == {"PY-E201", "PY-I101"}


class TestParseSuppressions:
    """Test parsing multiple suppressions from content."""

    def test_parse_multiple_suppressions(self):
        """Test parsing multiple directives."""
        content = """# ace:disable PY-E201
def foo():
    pass
# ace:enable PY-E201
"""
        result = parse_suppressions(content)

        assert len(result) == 2
        assert result[0].line == 1
        assert result[0].enabled is False
        assert result[1].line == 4
        assert result[1].enabled is True

    def test_parse_mixed_scopes(self):
        """Test parsing different scope types."""
        content = """# ace:disable PY-E201
x = 1  # ace:disable-line PY-I101
# ace:disable-next-line PY-E201
y = 2
# ace:enable PY-E201
"""
        result = parse_suppressions(content)

        assert len(result) == 4
        assert result[0].scope == SuppressionScope.BLOCK
        assert result[1].scope == SuppressionScope.LINE
        assert result[2].scope == SuppressionScope.NEXT_LINE
        assert result[3].scope == SuppressionScope.BLOCK

    def test_parse_empty_content(self):
        """Test parsing content with no suppressions."""
        content = "def foo():\n    return 42\n"
        result = parse_suppressions(content)

        assert result == []

    def test_parse_preserves_order(self):
        """Test that suppressions are returned in order."""
        content = """# Line 1
# ace:disable PY-E201  # Line 2
# Line 3
# ace:disable PY-I101  # Line 4
# Line 5
# ace:enable PY-E201   # Line 6
"""
        result = parse_suppressions(content)

        assert len(result) == 3
        assert result[0].line == 2
        assert result[1].line == 4
        assert result[2].line == 6


class TestIsRuleSuppressed:
    """Test rule suppression checking logic."""

    def test_line_scope_same_line(self):
        """Test line-level suppression on same line."""
        suppressions = [
            Suppression(5, SuppressionScope.LINE, {"PY-E201"}, False)
        ]

        assert is_rule_suppressed("PY-E201", 5, suppressions) is True
        assert is_rule_suppressed("PY-E201", 4, suppressions) is False
        assert is_rule_suppressed("PY-E201", 6, suppressions) is False

    def test_next_line_scope(self):
        """Test next-line suppression."""
        suppressions = [
            Suppression(5, SuppressionScope.NEXT_LINE, {"PY-E201"}, False)
        ]

        assert is_rule_suppressed("PY-E201", 5, suppressions) is False
        assert is_rule_suppressed("PY-E201", 6, suppressions) is True
        assert is_rule_suppressed("PY-E201", 7, suppressions) is False

    def test_block_scope_single_rule(self):
        """Test block-level suppression for single rule."""
        suppressions = [
            Suppression(5, SuppressionScope.BLOCK, {"PY-E201"}, False),
            Suppression(15, SuppressionScope.BLOCK, {"PY-E201"}, True),
        ]

        # Before disable
        assert is_rule_suppressed("PY-E201", 4, suppressions) is False

        # During suppression
        assert is_rule_suppressed("PY-E201", 6, suppressions) is True
        assert is_rule_suppressed("PY-E201", 10, suppressions) is True
        assert is_rule_suppressed("PY-E201", 14, suppressions) is True

        # After enable
        assert is_rule_suppressed("PY-E201", 16, suppressions) is False
        assert is_rule_suppressed("PY-E201", 20, suppressions) is False

    def test_block_scope_all_rules(self):
        """Test block-level suppression for all rules."""
        suppressions = [
            Suppression(5, SuppressionScope.BLOCK, set(), False),  # All rules
        ]

        assert is_rule_suppressed("PY-E201", 6, suppressions) is True
        assert is_rule_suppressed("PY-I101", 6, suppressions) is True
        assert is_rule_suppressed("ANY-RULE", 6, suppressions) is True

    def test_multiple_rules_independently(self):
        """Test that different rules are tracked independently."""
        suppressions = [
            Suppression(5, SuppressionScope.BLOCK, {"PY-E201"}, False),
            Suppression(10, SuppressionScope.BLOCK, {"PY-I101"}, False),
            Suppression(15, SuppressionScope.BLOCK, {"PY-E201"}, True),
        ]

        # PY-E201 suppressed from line 5-14
        assert is_rule_suppressed("PY-E201", 6, suppressions) is True
        assert is_rule_suppressed("PY-E201", 14, suppressions) is True
        assert is_rule_suppressed("PY-E201", 16, suppressions) is False

        # PY-I101 suppressed from line 10 onwards
        assert is_rule_suppressed("PY-I101", 9, suppressions) is False
        assert is_rule_suppressed("PY-I101", 11, suppressions) is True
        assert is_rule_suppressed("PY-I101", 16, suppressions) is True

    def test_nested_suppressions(self):
        """Test nested disable/enable patterns."""
        suppressions = [
            Suppression(5, SuppressionScope.BLOCK, set(), False),  # Disable all
            Suppression(10, SuppressionScope.BLOCK, {"PY-E201"}, True),  # Enable one
            Suppression(15, SuppressionScope.BLOCK, set(), True),  # Enable all
        ]

        # All rules disabled 5-9
        assert is_rule_suppressed("PY-E201", 7, suppressions) is True
        assert is_rule_suppressed("PY-I101", 7, suppressions) is True

        # PY-E201 enabled at 10, but others still disabled
        assert is_rule_suppressed("PY-E201", 12, suppressions) is False
        assert is_rule_suppressed("PY-I101", 12, suppressions) is True

        # All enabled after 15
        assert is_rule_suppressed("PY-E201", 16, suppressions) is False
        assert is_rule_suppressed("PY-I101", 16, suppressions) is False

    def test_empty_suppressions(self):
        """Test with no suppressions."""
        assert is_rule_suppressed("PY-E201", 10, []) is False


class TestFilterFindings:
    """Test filtering findings by suppressions."""

    def test_filter_next_line_suppression(self):
        """Test filtering with next-line suppression."""
        findings = [
            UnifiedIssue(
                file="test.py",
                line=6,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test",
            ),
        ]
        suppressions = [
            Suppression(5, SuppressionScope.NEXT_LINE, {"PY-E201"}, False)
        ]

        result = filter_findings_by_suppressions(findings, suppressions)

        assert len(result) == 0

    def test_filter_keeps_unsuppressed(self):
        """Test that unsuppressed findings are kept."""
        findings = [
            UnifiedIssue(
                file="test.py",
                line=6,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test1",            ),
            UnifiedIssue(
                file="test.py",
                line=10,
                rule="PY-I101",
                severity=Severity.LOW,
                message="test2",            ),
        ]
        suppressions = [
            Suppression(5, SuppressionScope.NEXT_LINE, {"PY-E201"}, False)
        ]

        result = filter_findings_by_suppressions(findings, suppressions)

        assert len(result) == 1
        assert result[0].rule == "PY-I101"

    def test_filter_block_suppression(self):
        """Test filtering with block-level suppression."""
        findings = [
            UnifiedIssue(
                file="test.py",
                line=6,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test1",            ),
            UnifiedIssue(
                file="test.py",
                line=10,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test2",            ),
            UnifiedIssue(
                file="test.py",
                line=20,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test3",            ),
        ]
        suppressions = [
            Suppression(5, SuppressionScope.BLOCK, {"PY-E201"}, False),
            Suppression(15, SuppressionScope.BLOCK, {"PY-E201"}, True),
        ]

        result = filter_findings_by_suppressions(findings, suppressions)

        # Lines 6 and 10 suppressed, line 20 not
        assert len(result) == 1
        assert result[0].line == 20

    def test_filter_no_suppressions(self):
        """Test filtering with no suppressions."""
        findings = [
            UnifiedIssue(
                file="test.py",
                line=6,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test",            ),
        ]

        result = filter_findings_by_suppressions(findings, [])

        assert len(result) == 1

    def test_filter_all_rules(self):
        """Test filtering with all-rules suppression."""
        findings = [
            UnifiedIssue(
                file="test.py",
                line=6,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test1",            ),
            UnifiedIssue(
                file="test.py",
                line=7,
                rule="PY-I101",
                severity=Severity.LOW,
                message="test2",            ),
        ]
        suppressions = [
            Suppression(5, SuppressionScope.BLOCK, set(), False)  # All rules
        ]

        result = filter_findings_by_suppressions(findings, suppressions)

        assert len(result) == 0


class TestSuppressionDeterminism:
    """Test deterministic behavior of suppression system."""

    def test_same_content_same_result(self):
        """Test that same content produces same suppressions."""
        content = """# ace:disable PY-E201
def foo():
    pass
# ace:enable PY-E201
"""
        result1 = parse_suppressions(content)
        result2 = parse_suppressions(content)

        assert len(result1) == len(result2)
        for s1, s2 in zip(result1, result2):
            assert s1.line == s2.line
            assert s1.scope == s2.scope
            assert s1.rule_ids == s2.rule_ids
            assert s1.enabled == s2.enabled

    def test_filtering_idempotent(self):
        """Test that filtering is idempotent."""
        findings = [
            UnifiedIssue(
                file="test.py",
                line=6,
                rule="PY-E201",
                severity=Severity.MEDIUM,
                message="test",            ),
        ]
        suppressions = [
            Suppression(5, SuppressionScope.NEXT_LINE, {"PY-E201"}, False)
        ]

        result1 = filter_findings_by_suppressions(findings, suppressions)
        result2 = filter_findings_by_suppressions(findings, suppressions)

        assert result1 == result2
