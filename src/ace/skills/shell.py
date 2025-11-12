"""Shell skill - Shell script static analysis."""

from ace.uir import UnifiedIssue, create_uir


def analyze_shell_strict_mode(text: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze shell script for missing strict mode settings.

    Args:
        text: Shell script content
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    findings = []
    lines = text.splitlines()

    if not lines:
        return findings

    # Check if first line has bash shebang
    shebang = lines[0]
    if "bash" in shebang:
        # Check if script has strict mode in first 10 lines
        has_strict_mode = any("set -euo pipefail" in line for line in lines[:10])

        if not has_strict_mode:
            finding = create_uir(
                file=path,
                line=1,
                rule="SH-S001-MISSING-STRICT-MODE",
                severity="low",
                message="missing 'set -euo pipefail' in bash script",
                suggestion="Add 'set -euo pipefail' after shebang for safer bash execution",
                snippet="shebang without strict mode",
            )
            findings.append(finding)

    return findings


# ============================================================================
# Legacy stub functions (kept for compatibility)
# ============================================================================


def analyze_shell(file_path: str) -> list:
    """
    Analyze shell script for issues.

    Args:
        file_path: Path to shell script

    Returns:
        List of UIR findings
    """
    return []


def refactor_shell(file_path: str, findings: list) -> str:
    """
    Fix shell script issues (quoting, shellcheck warnings).

    Args:
        file_path: Path to shell script
        findings: List of findings to fix

    Returns:
        Refactored shell script
    """
    return ""


def validate_shell_syntax(script: str) -> bool:
    """
    Validate shell script syntax.

    Args:
        script: Shell script content

    Returns:
        True if valid syntax
    """
    return True
