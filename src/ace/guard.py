"""Patch Guard - Deterministic edit verification with automatic rollback.

Verifies that Python edits preserve AST equivalence and don't introduce parse errors.
If verification fails, auto-reverts via journal.
"""

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import libcst as cst


@dataclass
class GuardResult:
    """Result of patch guard verification."""

    passed: bool
    file: str
    before_content: str
    after_content: str
    errors: list[str]
    guard_type: str  # "parse", "ast_equiv", "cst_apply"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "file": self.file,
            "errors": self.errors,
            "guard_type": self.guard_type,
            "before_hash": hashlib.sha256(self.before_content.encode()).hexdigest()[:16],
            "after_hash": hashlib.sha256(self.after_content.encode()).hexdigest()[:16],
        }


def verify_python_parse(content: str) -> tuple[bool, list[str]]:
    """
    Verify Python code parses successfully.

    Args:
        content: Python code

    Returns:
        Tuple of (success, errors)
    """
    errors = []

    # Try ast.parse
    try:
        ast.parse(content)
    except SyntaxError as e:
        errors.append(f"SyntaxError: {e}")
        return False, errors

    # Try libcst.parse
    try:
        cst.parse_module(content)
    except Exception as e:
        errors.append(f"LibCST parse error: {e}")
        return False, errors

    return True, []


def verify_ast_equivalence(before: str, after: str) -> tuple[bool, list[str]]:
    """
    Verify AST equivalence between before and after code.

    This is a semantic check - the code should have the same meaning even if
    formatting changes.

    Args:
        before: Original code
        after: Modified code

    Returns:
        Tuple of (equivalent, errors)
    """
    errors = []

    try:
        ast_before = ast.parse(before)
        ast_after = ast.parse(after)
    except SyntaxError as e:
        errors.append(f"Parse error during AST comparison: {e}")
        return False, errors

    # Compare AST dumps (deterministic representation)
    dump_before = ast.dump(ast_before, annotate_fields=False, include_attributes=False)
    dump_after = ast.dump(ast_after, annotate_fields=False, include_attributes=False)

    if dump_before != dump_after:
        errors.append("AST structures differ (semantic change detected)")
        return False, errors

    return True, []


def verify_cst_roundtrip(content: str) -> tuple[bool, list[str]]:
    """
    Verify CST → code → CST roundtrip.

    Args:
        content: Python code

    Returns:
        Tuple of (success, errors)
    """
    errors = []

    try:
        # Parse to CST
        tree = cst.parse_module(content)

        # Convert back to code
        roundtrip_code = tree.code

        # Parse again
        tree2 = cst.parse_module(roundtrip_code)

        # Compare CST dumps
        if tree != tree2:
            errors.append("CST roundtrip produced different tree")
            return False, errors

    except Exception as e:
        errors.append(f"CST roundtrip error: {e}")
        return False, errors

    return True, []


def guard_python_edit(
    file_path: Path | str,
    before_content: str,
    after_content: str,
    strict: bool = True,
) -> GuardResult:
    """
    Guard Python edit with multiple verification layers.

    Verification layers:
    1. Parse check: After code must parse successfully
    2. AST equivalence: Before and after must have same AST (if strict=True)
    3. CST roundtrip: After code must roundtrip cleanly through CST

    Args:
        file_path: Path to file being edited
        before_content: Original content
        after_content: Modified content
        strict: If True, require AST equivalence (default: True)

    Returns:
        GuardResult with verification status
    """
    file_path_str = str(file_path)
    errors = []

    # Layer 1: Parse check
    parse_ok, parse_errors = verify_python_parse(after_content)
    if not parse_ok:
        return GuardResult(
            passed=False,
            file=file_path_str,
            before_content=before_content,
            after_content=after_content,
            errors=parse_errors,
            guard_type="parse",
        )

    # Layer 2: AST equivalence (if strict)
    if strict:
        ast_equiv, ast_errors = verify_ast_equivalence(before_content, after_content)
        if not ast_equiv:
            return GuardResult(
                passed=False,
                file=file_path_str,
                before_content=before_content,
                after_content=after_content,
                errors=ast_errors,
                guard_type="ast_equiv",
            )

    # Layer 3: CST roundtrip
    cst_ok, cst_errors = verify_cst_roundtrip(after_content)
    if not cst_ok:
        return GuardResult(
            passed=False,
            file=file_path_str,
            before_content=before_content,
            after_content=after_content,
            errors=cst_errors,
            guard_type="cst_apply",
        )

    # All checks passed
    return GuardResult(
        passed=True,
        file=file_path_str,
        before_content=before_content,
        after_content=after_content,
        errors=[],
        guard_type="all",
    )


def guard_file_edit(
    file_path: Path,
    after_content: str,
    strict: bool = True,
) -> GuardResult:
    """
    Guard file edit (reads before content from disk).

    Args:
        file_path: Path to file
        after_content: Modified content
        strict: If True, require AST equivalence

    Returns:
        GuardResult
    """
    # Read before content
    try:
        before_content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return GuardResult(
            passed=False,
            file=str(file_path),
            before_content="",
            after_content=after_content,
            errors=[f"Failed to read original file: {e}"],
            guard_type="read",
        )

    # Only guard Python files
    if file_path.suffix != ".py":
        # Pass-through for non-Python files
        return GuardResult(
            passed=True,
            file=str(file_path),
            before_content=before_content,
            after_content=after_content,
            errors=[],
            guard_type="non-python",
        )

    return guard_python_edit(file_path, before_content, after_content, strict)


def auto_revert_on_guard_fail(
    guard_result: GuardResult,
    journal_path: Path | None = None,
) -> bool:
    """
    Auto-revert file if guard fails (requires journal).

    Args:
        guard_result: GuardResult from guard check
        journal_path: Path to journal file (optional)

    Returns:
        True if reverted successfully, False otherwise
    """
    if guard_result.passed:
        return False  # Nothing to revert

    # Write original content back
    try:
        file_path = Path(guard_result.file)
        file_path.write_text(guard_result.before_content, encoding="utf-8")

        # If journal provided, log revert
        if journal_path:
            from ace.journal import Journal

            journal = Journal(journal_path)
            journal.log_entry({
                "type": "guard_revert",
                "file": guard_result.file,
                "guard_type": guard_result.guard_type,
                "errors": guard_result.errors,
            })

        return True

    except Exception:
        return False


def format_guard_error(guard_result: GuardResult) -> str:
    """
    Format guard error for display.

    Args:
        guard_result: GuardResult

    Returns:
        Formatted error message
    """
    lines = []
    lines.append("=" * 60)
    lines.append("🛡️  PATCH GUARD FAILED")
    lines.append("=" * 60)
    lines.append(f"File: {guard_result.file}")
    lines.append(f"Guard Type: {guard_result.guard_type}")
    lines.append("")
    lines.append("Errors:")
    for error in guard_result.errors:
        lines.append(f"  - {error}")
    lines.append("")
    lines.append("Action: Edit aborted and auto-reverted")
    lines.append("=" * 60)
    return "\n".join(lines)


def get_guard_summary(results: list[GuardResult]) -> dict[str, Any]:
    """
    Get summary of guard results.

    Args:
        results: List of GuardResult

    Returns:
        Summary dictionary
    """
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    failures_by_type = {}
    for result in results:
        if not result.passed:
            guard_type = result.guard_type
            failures_by_type[guard_type] = failures_by_type.get(guard_type, 0) + 1

    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / len(results) if results else 0.0,
        "failures_by_type": failures_by_type,
    }
