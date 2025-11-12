"""Markdown skill - Static analysis for Markdown files."""

from markdown_it import MarkdownIt

from ace.uir import UnifiedIssue, create_uir


def analyze_markdown_dangerous_commands(text: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze Markdown content for dangerous commands in fenced code blocks.

    Args:
        text: Markdown content
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    findings = []

    try:
        md = MarkdownIt()
        tokens = md.parse(text)

        for token in tokens:
            if token.type == "fence":
                # Check if this is a bash/sh code block
                lang = token.info.strip() if token.info else ""
                if lang in {"bash", "sh"}:
                    # Check for dangerous commands
                    if "rm -rf /" in token.content:
                        # Get line number from token.map if available
                        line = token.map[0] + 1 if token.map else 1

                        finding = create_uir(
                            file=path,
                            line=line,
                            rule="MD-S001-DANGEROUS-COMMAND",
                            severity="critical",
                            message="dangerous command in fenced block",
                            suggestion="Remove or guard dangerous rm -rf / command",
                            snippet="rm -rf /",
                        )
                        findings.append(finding)

    except Exception:
        # If parsing fails, return empty list
        pass

    return findings


# ============================================================================
# Legacy stub functions (kept for compatibility)
# ============================================================================


def analyze_markdown(file_path: str) -> list:
    """
    Analyze Markdown file for issues.

    Args:
        file_path: Path to Markdown file

    Returns:
        List of UIR findings (broken links, formatting issues)
    """
    return []


def refactor_markdown(file_path: str, findings: list) -> str:
    """
    Fix Markdown issues (broken links, formatting).

    Args:
        file_path: Path to Markdown file
        findings: List of findings to fix

    Returns:
        Refactored Markdown content
    """
    return ""


def validate_markdown(content: str) -> bool:
    """
    Validate Markdown syntax.

    Args:
        content: Markdown content

    Returns:
        True if valid
    """
    return True
