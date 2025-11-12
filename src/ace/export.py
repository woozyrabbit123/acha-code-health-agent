"""Export utilities for UIR, receipts, and proof packs."""

import difflib
import json
from typing import Any


def to_json(obj: Any) -> str:
    """
    Convert object to deterministic JSON string.

    Args:
        obj: Object to serialize (must be JSON-serializable)

    Returns:
        JSON string with sorted keys, no timestamps

    Examples:
        >>> to_json({"b": 2, "a": 1})
        '{\\n  "a": 1,\\n  "b": 2\\n}'
    """
    # Convert objects with to_dict() method
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict()

    # Convert lists of objects
    if isinstance(obj, list):
        obj = [item.to_dict() if hasattr(item, "to_dict") else item for item in obj]

    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def unified_diff(before: str, after: str, path: str) -> str:
    """
    Generate unified diff between before and after code.

    Args:
        before: Original source code
        after: Modified source code
        path: File path (for diff header)

    Returns:
        Unified diff string

    Examples:
        >>> diff = unified_diff("a\\nb\\n", "a\\nc\\n", "test.py")
        >>> "-b" in diff and "+c" in diff
        True
    """
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    diff_lines = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )

    return "".join(diff_lines)


def export_uir(findings: list, output_path: str) -> bool:
    """
    Export findings in UIR format.

    Args:
        findings: List of UIR findings
        output_path: Output file path

    Returns:
        True if successful
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(to_json(findings))
        return True
    except Exception:
        return False


def create_receipt(refactor_info: dict, output_path: str) -> str:
    """
    Create refactoring receipt with SHA256 hashes.

    Args:
        refactor_info: Refactoring metadata
        output_path: Receipt file path

    Returns:
        Receipt path
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(to_json(refactor_info))
        return output_path
    except Exception:
        return ""


def build_proof_pack(artifacts_dir: str, output_zip: str) -> str:
    """
    Build proof pack ZIP with all artifacts.

    Args:
        artifacts_dir: Directory containing artifacts
        output_zip: Output ZIP path

    Returns:
        Path to created ZIP
    """
    # Stub implementation - not needed for this sprint
    return ""
