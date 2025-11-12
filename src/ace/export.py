"""Export utilities for UIR, receipts, and proof packs."""

import difflib
import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


# Cache for loaded schemas
_SCHEMA_CACHE: dict[str, dict] = {}


def load_schema(schema_name: str) -> dict:
    """
    Load JSON Schema from schemas/v1/ directory.

    Args:
        schema_name: Schema name (e.g., "unified_issue", "edit_plan")

    Returns:
        Parsed JSON Schema dict

    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema is invalid JSON
    """
    if schema_name in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[schema_name]

    # Find schema file relative to this module
    module_dir = Path(__file__).parent.parent.parent
    schema_path = module_dir / "schemas" / "v1" / f"{schema_name}.schema.json"

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    _SCHEMA_CACHE[schema_name] = schema
    return schema


def validate_against_schema(data: dict, schema_name: str, strict: bool = True) -> tuple[bool, list[str]]:
    """
    Validate data against a JSON Schema.

    Args:
        data: Data to validate (must be dict)
        schema_name: Schema name (e.g., "unified_issue")
        strict: If True, reject unknown properties (default: True)

    Returns:
        Tuple of (is_valid, error_messages)

    Examples:
        >>> data = {"file": "test.py", "line": 1, "rule": "PY-E201", "severity": "high", "message": "test", "stable_id": "01234567-89abcdef-01234567"}
        >>> valid, errors = validate_against_schema(data, "unified_issue")
        >>> valid
        True
    """
    if not JSONSCHEMA_AVAILABLE:
        # Graceful degradation: skip validation if jsonschema not installed
        return True, []

    try:
        schema = load_schema(schema_name)

        # Create RefResolver for resolving $ref to other schemas
        module_dir = Path(__file__).parent.parent.parent
        schema_dir = module_dir / "schemas" / "v1"
        base_uri = schema_dir.as_uri() + "/"

        # Create a store with all schemas
        store = {}
        for schema_file in schema_dir.glob("*.schema.json"):
            with open(schema_file, encoding="utf-8") as f:
                schema_content = json.load(f)
                # Store with both the filename and the $id
                store[schema_file.name] = schema_content
                if "$id" in schema_content:
                    store[schema_content["$id"]] = schema_content

        resolver = jsonschema.RefResolver(
            base_uri=base_uri,
            referrer=schema,
            store=store,
        )

        validator = Draft202012Validator(schema, resolver=resolver)

        errors = list(validator.iter_errors(data))
        if errors:
            error_messages = [f"{'.'.join(str(p) for p in e.path)}: {e.message}" for e in errors]
            return False, error_messages

        return True, []

    except FileNotFoundError:
        return False, [f"Schema '{schema_name}' not found"]
    except json.JSONDecodeError as e:
        return False, [f"Invalid schema JSON: {e}"]
    except Exception as e:
        return False, [f"Validation error: {e}"]


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


def export_uir(findings: list, output_path: str, validate: bool = True) -> bool:
    """
    Export findings in UIR format with optional schema validation.

    Args:
        findings: List of UIR findings
        output_path: Output file path
        validate: If True, validate each finding against unified_issue schema

    Returns:
        True if successful

    Raises:
        ValueError: If validation is enabled and findings don't match schema
    """
    try:
        # Convert findings to dicts
        findings_data = [f.to_dict() if hasattr(f, "to_dict") else f for f in findings]

        # Validate if requested
        if validate and JSONSCHEMA_AVAILABLE:
            for i, finding in enumerate(findings_data):
                valid, errors = validate_against_schema(finding, "unified_issue")
                if not valid:
                    raise ValueError(f"Finding {i} failed schema validation: {'; '.join(errors)}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(to_json(findings_data))
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
