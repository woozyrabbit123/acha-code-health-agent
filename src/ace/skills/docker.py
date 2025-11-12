"""Docker skill - Detect-only rules for Dockerfile security and best practices.

Rules:
- DOCK-001: Base image uses :latest tag (unpinned)
- DOCK-002: Missing USER instruction (runs as root)
- DOCK-003: apt-get without -y or cleanup
"""

import re
from pathlib import Path

from ace.uir import Severity, UnifiedIssue, create_uir

# Rule IDs
RULE_LATEST_TAG = "DOCK-001-LATEST-TAG"
RULE_MISSING_USER = "DOCK-002-MISSING-USER"
RULE_APT_NO_CLEANUP = "DOCK-003-APT-NO-CLEANUP"


def analyze_dockerfile(file_path: Path | str, content: str) -> list[UnifiedIssue]:
    """
    Analyze Dockerfile for security and best practice issues.

    Args:
        file_path: Path to Dockerfile
        content: File content

    Returns:
        List of UnifiedIssue findings

    Examples:
        >>> content = "FROM python:latest\\nRUN apt-get install -y curl"
        >>> findings = analyze_dockerfile("Dockerfile", content)
        >>> len(findings) >= 2  # latest tag + missing USER
        True
    """
    file_path_str = str(file_path)
    findings = []
    lines = content.splitlines()

    # Track state
    has_user_instruction = False
    from_instructions = []

    for line_num, line in enumerate(lines, start=1):
        line_stripped = line.strip()

        # Skip comments and empty lines
        if not line_stripped or line_stripped.startswith("#"):
            continue

        # Check for FROM with :latest
        if line_stripped.upper().startswith("FROM "):
            # Reset USER tracking for each new FROM (multi-stage builds)
            has_user_instruction = False
            from_instructions.append((line_num, line_stripped))
            if ":latest" in line_stripped.lower() or (
                ":" not in line_stripped and "as " not in line_stripped.lower()
            ):
                # Either explicit :latest or no tag specified (defaults to :latest)
                findings.append(
                    create_uir(
                        file=file_path_str,
                        line=line_num,
                        rule=RULE_LATEST_TAG,
                        severity=Severity.MEDIUM,
                        message="Base image uses ':latest' tag (unpinned version)",
                        suggestion="Pin to specific version (e.g., python:3.11.5-slim)",
                        snippet=line_stripped[:100],
                    )
                )

        # Check for USER instruction
        if line_stripped.upper().startswith("USER "):
            has_user_instruction = True

        # Check for apt-get install without proper flags
        if "apt-get" in line_stripped.lower() and "install" in line_stripped.lower():
            # Check for missing -y flag
            if " install " in line_stripped.lower() and " -y" not in line_stripped:
                findings.append(
                    create_uir(
                        file=file_path_str,
                        line=line_num,
                        rule=RULE_APT_NO_CLEANUP,
                        severity=Severity.LOW,
                        message="apt-get install without -y flag (non-interactive)",
                        suggestion="Add -y flag: apt-get install -y <package>",
                        snippet=line_stripped[:100],
                    )
                )

            # Check for missing cleanup in same RUN or continuation
            # Look ahead for && rm -rf /var/lib/apt/lists/* pattern
            has_cleanup = False
            check_lines = []

            # Collect continuation lines (lines ending with \)
            current_idx = line_num - 1
            check_lines.append(lines[current_idx])
            while current_idx < len(lines) - 1 and lines[current_idx].rstrip().endswith("\\"):
                current_idx += 1
                check_lines.append(lines[current_idx])

            # Check if cleanup is present in collected lines
            full_command = " ".join(l.strip() for l in check_lines)
            if "rm -rf /var/lib/apt/lists" in full_command or "rm -rf /var/cache/apt" in full_command:
                has_cleanup = True

            if not has_cleanup:
                findings.append(
                    create_uir(
                        file=file_path_str,
                        line=line_num,
                        rule=RULE_APT_NO_CLEANUP,
                        severity=Severity.LOW,
                        message="apt-get install without cleanup (increases image size)",
                        suggestion="Add cleanup: && rm -rf /var/lib/apt/lists/*",
                        snippet=line_stripped[:100],
                    )
                )

    # Check for missing USER after final FROM
    if from_instructions and not has_user_instruction:
        # Report on last FROM line
        last_from_line, last_from_text = from_instructions[-1]
        findings.append(
            create_uir(
                file=file_path_str,
                line=last_from_line,
                rule=RULE_MISSING_USER,
                severity=Severity.HIGH,
                message="Dockerfile missing USER instruction (runs as root)",
                suggestion="Add USER instruction: USER nonroot",
                snippet=last_from_text[:100],
            )
        )

    return findings


def is_dockerfile(file_path: Path) -> bool:
    """
    Check if file is a Dockerfile.

    Args:
        file_path: Path to check

    Returns:
        True if file is a Dockerfile

    Examples:
        >>> is_dockerfile(Path("Dockerfile"))
        True
        >>> is_dockerfile(Path("Dockerfile.prod"))
        True
        >>> is_dockerfile(Path("docker/Dockerfile"))
        True
        >>> is_dockerfile(Path("test.py"))
        False
    """
    name = file_path.name.lower()
    return name == "dockerfile" or name.startswith("dockerfile.")


def analyze_docker_file(file_path: Path) -> list[UnifiedIssue]:
    """
    Analyze Docker file (wrapper for external use).

    Args:
        file_path: Path to Dockerfile

    Returns:
        List of findings
    """
    if not file_path.exists():
        return []

    if not is_dockerfile(file_path):
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
        return analyze_dockerfile(file_path, content)
    except Exception:
        return []


def get_docker_rules() -> list[str]:
    """
    Get list of Docker rule IDs.

    Returns:
        List of rule IDs
    """
    return [
        RULE_LATEST_TAG,
        RULE_MISSING_USER,
        RULE_APT_NO_CLEANUP,
    ]


def get_docker_rule_info() -> dict[str, dict[str, str]]:
    """
    Get information about Docker rules.

    Returns:
        Dictionary mapping rule ID to info dict
    """
    return {
        RULE_LATEST_TAG: {
            "id": RULE_LATEST_TAG,
            "severity": "medium",
            "description": "Base image uses ':latest' tag (unpinned version)",
            "rationale": "Latest tag is mutable and can lead to inconsistent builds",
            "fix": "Pin to specific version tag",
        },
        RULE_MISSING_USER: {
            "id": RULE_MISSING_USER,
            "severity": "high",
            "description": "Dockerfile missing USER instruction (runs as root)",
            "rationale": "Running as root increases security risk",
            "fix": "Add USER instruction to run as non-root",
        },
        RULE_APT_NO_CLEANUP: {
            "id": RULE_APT_NO_CLEANUP,
            "severity": "low",
            "description": "apt-get without proper flags or cleanup",
            "rationale": "Missing -y causes interactive prompts; no cleanup increases image size",
            "fix": "Use -y flag and clean up apt cache",
        },
    }
