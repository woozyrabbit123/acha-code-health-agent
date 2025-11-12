"""Suppression directive parsing for inline rule disabling.

Supports suppression comments in multiple languages:
- Python: # ace:disable RULE-ID
- Markdown: <!-- ace:disable RULE-ID -->
- YAML: # ace:disable RULE-ID
- Shell: # ace:disable RULE-ID
"""

import re
from dataclasses import dataclass
from enum import Enum


class SuppressionScope(Enum):
    """Scope of a suppression directive."""

    LINE = "line"  # Suppress on current line only
    NEXT_LINE = "next-line"  # Suppress on next line only
    BLOCK = "block"  # Suppress until re-enabled


@dataclass
class Suppression:
    """
    A suppression directive found in code.

    Attributes:
        line: Line number where directive appears
        scope: Scope of suppression (line/next-line/block)
        rule_ids: Set of rule IDs to suppress (empty = all rules)
        enabled: True for enable directive, False for disable
    """

    line: int
    scope: SuppressionScope
    rule_ids: set[str]
    enabled: bool


# Regex patterns for suppression directives
# Matches: ace:disable, ace:disable-line, ace:disable-next-line, ace:enable
SUPPRESSION_PATTERN = re.compile(
    r"ace:(disable-next-line|disable-line|disable|enable)(?:\s+([A-Z0-9,\-\s]+))?",
    re.IGNORECASE,
)


def parse_suppression_directive(line: str, line_number: int) -> Suppression | None:
    """
    Parse a suppression directive from a line of code.

    Args:
        line: Line of code (may contain comment)
        line_number: Line number (1-indexed)

    Returns:
        Suppression object if directive found, None otherwise

    Examples:
        >>> parse_suppression_directive("# ace:disable PY-E201", 10)
        Suppression(line=10, scope=<SuppressionScope.BLOCK: 'block'>, rule_ids={'PY-E201'}, enabled=False)

        >>> parse_suppression_directive("# ace:disable-next-line PY-E201,PY-I101", 5)
        Suppression(line=5, scope=<SuppressionScope.NEXT_LINE: 'next-line'>, rule_ids={'PY-E201', 'PY-I101'}, enabled=False)

        >>> parse_suppression_directive("# ace:enable PY-E201", 20)
        Suppression(line=20, scope=<SuppressionScope.BLOCK: 'block'>, rule_ids={'PY-E201'}, enabled=True)

        >>> parse_suppression_directive("regular code", 1)
    """
    match = SUPPRESSION_PATTERN.search(line)
    if not match:
        return None

    directive = match.group(1).lower()
    rule_ids_str = match.group(2)

    # Parse rule IDs - strip and clean  up
    if rule_ids_str:
        # Split by comma and clean each ID
        rule_ids = set()
        for rid in rule_ids_str.split(","):
            # Strip whitespace and remove non-alphanumeric trailing chars (like -->)
            cleaned = rid.strip().rstrip("-><!/ ")
            if cleaned and not cleaned.endswith("-"):
                rule_ids.add(cleaned)
    else:
        rule_ids = set()  # Empty = all rules

    # Determine scope and enabled status
    if directive == "enable":
        scope = SuppressionScope.BLOCK
        enabled = True
    elif directive == "disable-line":
        scope = SuppressionScope.LINE
        enabled = False
    elif directive == "disable-next-line":
        scope = SuppressionScope.NEXT_LINE
        enabled = False
    else:  # "disable"
        scope = SuppressionScope.BLOCK
        enabled = False

    return Suppression(
        line=line_number, scope=scope, rule_ids=rule_ids, enabled=enabled
    )


def parse_suppressions(content: str) -> list[Suppression]:
    """
    Parse all suppression directives from file content.

    Args:
        content: File content as string

    Returns:
        List of Suppression objects in order of appearance

    Examples:
        >>> content = '''# ace:disable PY-E201
        ... def foo():
        ...     pass
        ... # ace:enable PY-E201
        ... '''
        >>> sups = parse_suppressions(content)
        >>> len(sups)
        2
        >>> sups[0].enabled
        False
        >>> sups[1].enabled
        True
    """
    suppressions = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        suppression = parse_suppression_directive(line, line_num)
        if suppression:
            suppressions.append(suppression)

    return suppressions


def is_rule_suppressed(
    rule_id: str, line: int, suppressions: list[Suppression]
) -> bool:
    """
    Check if a rule is suppressed at a given line.

    Args:
        rule_id: Rule ID to check (e.g., "PY-E201")
        line: Line number to check (1-indexed)
        suppressions: List of suppressions from parse_suppressions()

    Returns:
        True if rule is suppressed at this line

    Examples:
        >>> suppressions = [
        ...     Suppression(5, SuppressionScope.NEXT_LINE, {"PY-E201"}, False),
        ...     Suppression(10, SuppressionScope.BLOCK, {"PY-I101"}, False),
        ... ]
        >>> is_rule_suppressed("PY-E201", 6, suppressions)
        True
        >>> is_rule_suppressed("PY-E201", 7, suppressions)
        False
        >>> is_rule_suppressed("PY-I101", 11, suppressions)
        True
        >>> is_rule_suppressed("PY-I101", 9, suppressions)
        False
    """
    # Track block-level suppressions and explicit enables
    block_disabled: set[str] = set()  # Disabled rules (or "*" for all)
    block_enabled: set[str] = set()  # Explicitly enabled rules (overrides "*")

    for suppression in suppressions:
        # Stop if we've passed the target line
        if suppression.line > line:
            break

        if suppression.scope == SuppressionScope.LINE:
            # Line-level: only affects the directive's own line
            if suppression.line == line:
                if not suppression.rule_ids:  # All rules
                    return True
                if rule_id in suppression.rule_ids:
                    return True

        elif suppression.scope == SuppressionScope.NEXT_LINE:
            # Next-line: affects the following line
            if suppression.line + 1 == line:
                if not suppression.rule_ids:  # All rules
                    return True
                if rule_id in suppression.rule_ids:
                    return True

        elif suppression.scope == SuppressionScope.BLOCK:
            # Block-level: track state changes
            if not suppression.rule_ids:
                # Affects all rules
                if suppression.enabled:
                    block_disabled.clear()
                    block_enabled.clear()
                else:
                    block_disabled.add("*")
            else:
                # Affects specific rules
                for rid in suppression.rule_ids:
                    if suppression.enabled:
                        block_disabled.discard(rid)
                        block_enabled.add(rid)
                    else:
                        block_enabled.discard(rid)
                        block_disabled.add(rid)

    # Check block-level suppressions
    # If explicitly enabled, not suppressed
    if rule_id in block_enabled:
        return False

    # If all rules disabled and this rule not explicitly enabled
    if "*" in block_disabled:
        return True

    # If this specific rule disabled
    if rule_id in block_disabled:
        return True

    return False


def filter_findings_by_suppressions(
    findings: list, suppressions: list[Suppression]
) -> list:
    """
    Filter findings by removing suppressed ones.

    Args:
        findings: List of UnifiedIssue objects
        suppressions: List of suppressions from parse_suppressions()

    Returns:
        Filtered list with suppressed findings removed

    Examples:
        >>> from ace.uir import UnifiedIssue, Severity
        >>> findings = [
        ...     UnifiedIssue(file="test.py", line=6, rule="PY-E201",
        ...                  severity=Severity.MEDIUM, message="test",
        ...                  stable_id="abc123"),
        ... ]
        >>> suppressions = [
        ...     Suppression(5, SuppressionScope.NEXT_LINE, {"PY-E201"}, False),
        ... ]
        >>> filtered = filter_findings_by_suppressions(findings, suppressions)
        >>> len(filtered)
        0
    """
    if not suppressions:
        return findings

    filtered = []
    for finding in findings:
        if not is_rule_suppressed(finding.rule, finding.line, suppressions):
            filtered.append(finding)

    return filtered
