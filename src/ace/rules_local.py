"""
Local rules version management for deterministic offline upgrades.

Manages .ace/rules.json with embedded metadata and canonical ordering.
"""

import hashlib
import json
from pathlib import Path

# Local rules version (bump this to trigger upgrades)
RULES_VERSION = "1.1.0"

# Canonical rule catalog with metadata
RULES_CATALOG = [
    {
        "id": "PY-S101-UNSAFE-HTTP",
        "category": "security",
        "severity": "high",
        "description": "HTTP requests without timeout can hang indefinitely",
        "autofix": True,
    },
    {
        "id": "PY-E201-BROAD-EXCEPT",
        "category": "exceptions",
        "severity": "medium",
        "description": "Bare except catches all errors including system exits",
        "autofix": True,
    },
    {
        "id": "PY-I101-IMPORT-SORT",
        "category": "style",
        "severity": "low",
        "description": "Imports should be sorted for consistency",
        "autofix": True,
    },
    {
        "id": "PY-S201-SUBPROCESS-CHECK",
        "category": "security",
        "severity": "high",
        "description": "subprocess.run() without check=True ignores errors",
        "autofix": True,
    },
    {
        "id": "PY-S202-SUBPROCESS-SHELL",
        "category": "security",
        "severity": "high",
        "description": "shell=True is dangerous with user input",
        "autofix": False,
    },
    {
        "id": "PY-S203-SUBPROCESS-STRING-CMD",
        "category": "security",
        "severity": "high",
        "description": "String commands with shell are vulnerable to injection",
        "autofix": False,
    },
    {
        "id": "PY-S310-TRAILING-WS",
        "category": "style",
        "severity": "low",
        "description": "Trailing whitespace should be removed",
        "autofix": True,
    },
    {
        "id": "PY-S311-EOF-NL",
        "category": "style",
        "severity": "low",
        "description": "Files should end with a newline",
        "autofix": True,
    },
    {
        "id": "PY-S312-BLANKLINES",
        "category": "style",
        "severity": "low",
        "description": "Excessive blank lines reduce readability",
        "autofix": True,
    },
    {
        "id": "PY-Q201-ASSERT-IN-NONTEST",
        "category": "quality",
        "severity": "medium",
        "description": "assert is for tests only, use proper error handling",
        "autofix": False,
    },
    {
        "id": "PY-Q202-PRINT-IN-SRC",
        "category": "quality",
        "severity": "low",
        "description": "print() should be replaced with proper logging",
        "autofix": False,
    },
    {
        "id": "PY-Q203-EVAL-EXEC",
        "category": "quality",
        "severity": "high",
        "description": "eval() and exec() are dangerous",
        "autofix": False,
    },
    {
        "id": "MD-S001-DANGEROUS-COMMAND",
        "category": "security",
        "severity": "medium",
        "description": "Dangerous shell commands in markdown",
        "autofix": False,
    },
    {
        "id": "YML-F001-DUPLICATE-KEY",
        "category": "format",
        "severity": "high",
        "description": "Duplicate YAML keys cause undefined behavior",
        "autofix": False,
    },
    {
        "id": "SH-S001-MISSING-STRICT-MODE",
        "category": "security",
        "severity": "high",
        "description": "Shell scripts should use 'set -euo pipefail'",
        "autofix": False,
    },
]


def bump_rules_version(rules_path: Path = Path(".ace/rules.json")) -> None:
    """
    Bump local rules version and rewrite rules.json deterministically.

    This is a deterministic offline operation that:
    1. Increments the version in the file
    2. Re-sorts the catalog by ID
    3. Invalidates cache (by changing content hash)

    Args:
        rules_path: Path to rules.json file
    """
    # Ensure .ace directory exists
    rules_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort catalog by ID for deterministic output
    sorted_catalog = sorted(RULES_CATALOG, key=lambda r: r["id"])

    # Create rules document
    rules_doc = {
        "version": RULES_VERSION,
        "updated": "local",  # No timestamp for determinism
        "rules": sorted_catalog,
    }

    # Compute content hash for cache invalidation
    content_str = json.dumps(rules_doc, sort_keys=True)
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:8]

    rules_doc["content_hash"] = content_hash

    # Write with deterministic formatting
    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump(rules_doc, f, indent=2, sort_keys=True)
        f.write("\n")  # Trailing newline


def load_rules(rules_path: Path = Path(".ace/rules.json")) -> dict:
    """
    Load rules from rules.json.

    Args:
        rules_path: Path to rules.json file

    Returns:
        Rules document dict

    Raises:
        FileNotFoundError: If rules.json doesn't exist
    """
    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")

    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_rules_version(rules_path: Path = Path(".ace/rules.json")) -> str:
    """
    Get current rules version from rules.json.

    Args:
        rules_path: Path to rules.json file

    Returns:
        Version string, or "unknown" if file doesn't exist
    """
    try:
        rules = load_rules(rules_path)
        return rules.get("version", "unknown")
    except FileNotFoundError:
        return "unknown"


def init_rules(rules_path: Path = Path(".ace/rules.json")) -> None:
    """
    Initialize rules.json if it doesn't exist.

    Args:
        rules_path: Path to rules.json file
    """
    if not rules_path.exists():
        bump_rules_version(rules_path)
