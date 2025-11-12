"""GitHub Actions skill - Detect-only rules for GHA workflow security.

Rules:
- GHA-001: Unpinned action uses (not pinned to SHA)
- GHA-002: permissions: write-all (overly permissive)
- GHA-003: Missing permissions declaration (implicit write-all)
"""

import re
from pathlib import Path

import yaml

from ace.uir import Severity, UnifiedIssue, create_uir

# Rule IDs
RULE_UNPINNED_ACTION = "GHA-001-UNPINNED-ACTION"
RULE_WRITE_ALL = "GHA-002-WRITE-ALL"
RULE_MISSING_PERMISSIONS = "GHA-003-MISSING-PERMISSIONS"


def analyze_github_workflow(file_path: Path | str, content: str) -> list[UnifiedIssue]:
    """
    Analyze GitHub Actions workflow for security issues.

    Args:
        file_path: Path to workflow YAML file
        content: File content

    Returns:
        List of UnifiedIssue findings
    """
    file_path_str = str(file_path)
    findings = []

    try:
        data = yaml.safe_load(content)
    except Exception:
        # Invalid YAML - skip analysis
        return []

    if not isinstance(data, dict):
        return []

    # Check for top-level permissions
    has_top_level_permissions = "permissions" in data

    # Get all jobs
    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        return []

    # Track if any job has write permissions without explicit declaration
    any_job_without_permissions = False

    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue

        # Check job-level permissions
        job_permissions = job_config.get("permissions")

        if job_permissions is None and not has_top_level_permissions:
            any_job_without_permissions = True

        # Check for write-all
        if isinstance(job_permissions, str) and job_permissions == "write-all":
            findings.append(
                create_uir(
                    file=file_path_str,
                    line=1,  # Can't determine exact line from parsed YAML
                    rule=RULE_WRITE_ALL,
                    severity=Severity.HIGH,
                    message=f"Job '{job_name}' uses permissions: write-all (overly permissive)",
                    suggestion="Use minimal permissions: permissions: { contents: read, ... }",
                    snippet=f"job: {job_name}",
                )
            )

        # Check for unpinned actions in steps
        steps = job_config.get("steps", [])
        if not isinstance(steps, list):
            continue

        for step_idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            uses = step.get("uses", "")
            if not uses:
                continue

            # Check if action is pinned to SHA
            # Format: owner/repo@ref
            # Safe: owner/repo@<40-char-hex-sha>
            # Unsafe: owner/repo@v1, owner/repo@main, etc.

            # Skip local actions (./)
            if uses.startswith("./"):
                continue

            # Extract ref part
            if "@" in uses:
                action_path, ref = uses.rsplit("@", 1)

                # Check if ref is a SHA (40 hex chars)
                is_sha = bool(re.match(r"^[a-f0-9]{40}$", ref))

                if not is_sha:
                    findings.append(
                        create_uir(
                            file=file_path_str,
                            line=1,  # Can't determine exact line
                            rule=RULE_UNPINNED_ACTION,
                            severity=Severity.MEDIUM,
                            message=f"Action '{uses}' not pinned to SHA (uses mutable ref '{ref}')",
                            suggestion=f"Pin to SHA: {action_path}@<full-sha>",
                            snippet=uses[:100],
                        )
                    )

    # Check for missing top-level permissions when no jobs have them
    if any_job_without_permissions and not has_top_level_permissions:
        findings.append(
            create_uir(
                file=file_path_str,
                line=1,
                rule=RULE_MISSING_PERMISSIONS,
                severity=Severity.MEDIUM,
                message="Workflow missing permissions declaration (defaults to write-all for classic workflows)",
                suggestion="Add top-level: permissions: { contents: read }",
                snippet="(workflow level)",
            )
        )

    return findings


def is_github_workflow(file_path: Path) -> bool:
    """
    Check if file is a GitHub Actions workflow.

    Args:
        file_path: Path to check

    Returns:
        True if file is a GHA workflow

    Examples:
        >>> is_github_workflow(Path(".github/workflows/ci.yml"))
        True
        >>> is_github_workflow(Path(".github/workflows/test.yaml"))
        True
        >>> is_github_workflow(Path("test.yml"))
        False
    """
    # Must be in .github/workflows/
    parts = file_path.parts
    if len(parts) < 3:
        return False

    # Check if path contains .github/workflows/
    try:
        workflows_idx = parts.index("workflows")
        if workflows_idx > 0 and parts[workflows_idx - 1] == ".github":
            # Must be .yml or .yaml
            return file_path.suffix in (".yml", ".yaml")
    except ValueError:
        pass

    return False


def analyze_gha_file(file_path: Path) -> list[UnifiedIssue]:
    """
    Analyze GitHub Actions workflow file (wrapper for external use).

    Args:
        file_path: Path to workflow file

    Returns:
        List of findings
    """
    if not file_path.exists():
        return []

    if not is_github_workflow(file_path):
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
        return analyze_github_workflow(file_path, content)
    except Exception:
        return []


def get_gha_rules() -> list[str]:
    """
    Get list of GHA rule IDs.

    Returns:
        List of rule IDs
    """
    return [
        RULE_UNPINNED_ACTION,
        RULE_WRITE_ALL,
        RULE_MISSING_PERMISSIONS,
    ]


def get_gha_rule_info() -> dict[str, dict[str, str]]:
    """
    Get information about GHA rules.

    Returns:
        Dictionary mapping rule ID to info dict
    """
    return {
        RULE_UNPINNED_ACTION: {
            "id": RULE_UNPINNED_ACTION,
            "severity": "medium",
            "description": "Action not pinned to SHA (uses mutable ref)",
            "rationale": "Mutable refs (v1, main) can change, leading to supply chain attacks",
            "fix": "Pin to full SHA commit hash",
        },
        RULE_WRITE_ALL: {
            "id": RULE_WRITE_ALL,
            "severity": "high",
            "description": "Workflow uses permissions: write-all",
            "rationale": "Overly permissive; violates principle of least privilege",
            "fix": "Use minimal required permissions",
        },
        RULE_MISSING_PERMISSIONS: {
            "id": RULE_MISSING_PERMISSIONS,
            "severity": "medium",
            "description": "Workflow missing permissions declaration",
            "rationale": "Defaults to write-all for classic workflows",
            "fix": "Explicitly declare minimal permissions",
        },
    }
