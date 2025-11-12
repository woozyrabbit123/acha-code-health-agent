"""Config skill - YAML/TOML/JSON analysis and formatting."""

import yaml

from ace.uir import UnifiedIssue, create_uir


def analyze_yaml_duplicate_keys(text: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze YAML content for duplicate keys.

    Args:
        text: YAML content
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    findings = []

    # Simple line-by-line scan for duplicate keys
    # This catches duplicate keys at the same indentation level
    seen_keys = {}
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        # Skip comments and empty lines
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        # Check if this looks like a key: value pair
        if ":" in line and not line.lstrip().startswith("-"):
            # Extract the key
            key_part = line.split(":", 1)[0].strip()

            # Calculate indentation level
            indent = len(line) - len(line.lstrip())

            # Create a unique identifier for key + indentation
            key_id = (key_part, indent)

            if key_id in seen_keys:
                # Found a duplicate
                finding = create_uir(
                    file=path,
                    line=i,
                    rule="YML-F001-DUPLICATE-KEY",
                    severity="medium",
                    message=f"duplicate key: {key_part}",
                    suggestion=f"Remove or rename duplicate key '{key_part}'",
                    snippet=key_part,
                )
                findings.append(finding)
            else:
                seen_keys[key_id] = i

    return findings


# ============================================================================
# Legacy stub functions (kept for compatibility)
# ============================================================================


def analyze_config(file_path: str, config_type: str) -> list:
    """
    Analyze configuration file for issues.

    Args:
        file_path: Path to config file
        config_type: Type of config (yaml, toml, json)

    Returns:
        List of UIR findings
    """
    return []


def refactor_config(file_path: str, findings: list, config_type: str) -> str:
    """
    Fix configuration issues (key sorting, schema validation).

    Args:
        file_path: Path to config file
        findings: List of findings to fix
        config_type: Type of config

    Returns:
        Refactored config content
    """
    return ""


def validate_config(content: str, config_type: str) -> bool:
    """
    Validate config file syntax.

    Args:
        content: Config file content
        config_type: Type of config

    Returns:
        True if valid
    """
    try:
        if config_type == "yaml":
            yaml.safe_load(content)
            return True
    except Exception:
        return False
    return True
