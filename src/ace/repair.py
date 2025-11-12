"""
Repair engine for ACE - isolates failing edits and salvages safe subsets.

When a pack edit fails guard/invariants, this module uses binary search
to isolate the failing edit(s), commits the safe subset, and generates
a repair plan for manual review.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ace.fileio import write_text_preserving_style
from ace.guard import GuardResult, guard_python_edit
from ace.safety import atomic_write


@dataclass
class RepairReport:
    """Report for a repair operation."""

    run_id: str
    file: str
    total_edits: int
    safe_edits: int
    failed_edits: int
    safe_edit_indices: list[int]
    failed_edit_indices: list[int]
    guard_failure_reason: str
    repair_suggestions: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "file": self.file,
            "total_edits": self.total_edits,
            "safe_edits": self.safe_edits,
            "failed_edits": self.failed_edits,
            "safe_edit_indices": self.safe_edit_indices,
            "failed_edit_indices": self.failed_edit_indices,
            "guard_failure_reason": self.guard_failure_reason,
            "repair_suggestions": self.repair_suggestions,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: dict) -> "RepairReport":
        """Create from dictionary."""
        return RepairReport(
            run_id=data["run_id"],
            file=data["file"],
            total_edits=data["total_edits"],
            safe_edits=data["safe_edits"],
            failed_edits=data["failed_edits"],
            safe_edit_indices=data["safe_edit_indices"],
            failed_edit_indices=data["failed_edit_indices"],
            guard_failure_reason=data["guard_failure_reason"],
            repair_suggestions=data.get("repair_suggestions", []),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class RepairResult:
    """Result of a repair attempt."""

    success: bool
    content: str  # Final content (with safe edits applied)
    report: RepairReport | None = None
    partial_apply: bool = False  # True if some edits were skipped


def try_apply_with_repair(
    file_path: Path,
    edits: list,
    original_content: str,
    guard_fn: Callable[[Path, str, str], GuardResult],
    run_id: str = "",
) -> RepairResult:
    """
    Try to apply edits with automatic repair if guard fails.

    Algorithm:
    1. Attempt to apply all edits → if guard OK → done
    2. If guard fails, use binary search to isolate failing edits
    3. Apply safe subset (complement of failing edits)
    4. Generate repair report for failed edits

    Args:
        file_path: Path to file being modified
        edits: List of Edit objects to apply
        original_content: Original file content
        guard_fn: Guard function (file_path, before, after) -> GuardResult
        run_id: Run identifier for repair report

    Returns:
        RepairResult with success status and final content
    """
    if not edits:
        return RepairResult(
            success=True,
            content=original_content,
            partial_apply=False
        )

    # Sort edits by start line for deterministic order
    sorted_edits = sorted(edits, key=lambda e: e.start_line)

    # Step 1: Try applying all edits
    merged_content = _apply_edits_subset(original_content, sorted_edits, range(len(sorted_edits)))
    guard_result = guard_fn(file_path, original_content, merged_content)

    if guard_result.passed:
        # All edits passed guard
        return RepairResult(
            success=True,
            content=merged_content,
            partial_apply=False
        )

    # Step 2: Guard failed - use binary search to isolate failing edits
    failed_indices = _binary_search_failing_edits(
        original_content,
        sorted_edits,
        guard_fn,
        file_path
    )

    # Step 3: Apply safe subset (all indices except failed ones)
    safe_indices = [i for i in range(len(sorted_edits)) if i not in failed_indices]

    if not safe_indices:
        # All edits failed - return original content
        report = RepairReport(
            run_id=run_id,
            file=str(file_path),
            total_edits=len(sorted_edits),
            safe_edits=0,
            failed_edits=len(sorted_edits),
            safe_edit_indices=[],
            failed_edit_indices=list(failed_indices),
            guard_failure_reason=_format_guard_error(guard_result),
            repair_suggestions=[
                "All edits failed guard checks",
                "Review the rule logic or file structure",
                "Consider filing a bug report if this seems incorrect"
            ],
            timestamp=_get_timestamp()
        )

        return RepairResult(
            success=False,
            content=original_content,
            report=report,
            partial_apply=False
        )

    # Apply safe subset
    safe_content = _apply_edits_subset(original_content, sorted_edits, safe_indices)

    # Verify safe subset passes guard
    safe_guard_result = guard_fn(file_path, original_content, safe_content)

    if not safe_guard_result.passed:
        # Safe subset also fails - this shouldn't happen with correct binary search
        # Fall back to original content
        report = RepairReport(
            run_id=run_id,
            file=str(file_path),
            total_edits=len(sorted_edits),
            safe_edits=0,
            failed_edits=len(sorted_edits),
            safe_edit_indices=[],
            failed_edit_indices=list(range(len(sorted_edits))),
            guard_failure_reason="Safe subset verification failed (binary search error)",
            repair_suggestions=[
                "Binary search isolated incorrect subset",
                "This is a bug - please report it",
                "Reverting to original content for safety"
            ],
            timestamp=_get_timestamp()
        )

        return RepairResult(
            success=False,
            content=original_content,
            report=report,
            partial_apply=False
        )

    # Step 4: Generate repair report
    report = RepairReport(
        run_id=run_id,
        file=str(file_path),
        total_edits=len(sorted_edits),
        safe_edits=len(safe_indices),
        failed_edits=len(failed_indices),
        safe_edit_indices=safe_indices,
        failed_edit_indices=list(failed_indices),
        guard_failure_reason=_format_guard_error(guard_result),
        repair_suggestions=_generate_repair_suggestions(
            sorted_edits,
            failed_indices,
            guard_result
        ),
        timestamp=_get_timestamp()
    )

    return RepairResult(
        success=True,
        content=safe_content,
        report=report,
        partial_apply=True
    )


def _apply_edits_subset(
    original_content: str,
    edits: list,
    indices: list[int] | range
) -> str:
    """
    Apply a subset of edits to content.

    Args:
        original_content: Original content
        edits: List of all edits (sorted by start_line)
        indices: Indices of edits to apply

    Returns:
        Content with specified edits applied
    """
    # For simplicity, assume each edit has a 'payload' field with full content
    # In real implementation, this would need to handle line-based merging
    if not indices:
        return original_content

    # If only one edit and it has full content replacement, use it
    if len(indices) == 1:
        edit = edits[indices[0]]
        if hasattr(edit, 'payload'):
            return edit.payload

    # For multiple edits, we need to merge them
    # Current ACE plans typically have one edit with full file replacement
    # So we take the last edit's payload
    for i in reversed(list(indices)):
        edit = edits[i]
        if hasattr(edit, 'payload'):
            return edit.payload

    return original_content


def _binary_search_failing_edits(
    original_content: str,
    edits: list,
    guard_fn: Callable,
    file_path: Path
) -> set[int]:
    """
    Use binary search to isolate failing edits.

    Args:
        original_content: Original content
        edits: List of edits (sorted by start_line)
        guard_fn: Guard function
        file_path: File path for guard

    Returns:
        Set of indices of failing edits
    """
    n = len(edits)
    if n == 0:
        return set()

    if n == 1:
        # Only one edit - it must be the failing one
        return {0}

    # Binary search: try first half vs second half
    mid = n // 2

    # Try first half
    first_half_content = _apply_edits_subset(original_content, edits, range(mid))
    first_half_result = guard_fn(file_path, original_content, first_half_content)

    # Try second half
    second_half_content = _apply_edits_subset(original_content, edits, range(mid, n))
    second_half_result = guard_fn(file_path, original_content, second_half_content)

    failing_indices = set()

    if not first_half_result.passed:
        # First half has failures - recurse
        failing_indices.update(
            _binary_search_failing_edits(
                original_content,
                edits[:mid],
                guard_fn,
                file_path
            )
        )

    if not second_half_result.passed:
        # Second half has failures - recurse with offset
        sub_failures = _binary_search_failing_edits(
            original_content,
            edits[mid:],
            guard_fn,
            file_path
        )
        # Offset indices by mid
        failing_indices.update(idx + mid for idx in sub_failures)

    return failing_indices


def _format_guard_error(guard_result: GuardResult) -> str:
    """Format guard failure reason."""
    if not guard_result.errors:
        return f"Guard failed: {guard_result.guard_type}"

    return f"{guard_result.guard_type}: {'; '.join(guard_result.errors[:3])}"


def _generate_repair_suggestions(
    edits: list,
    failed_indices: list[int],
    guard_result: GuardResult
) -> list[str]:
    """Generate repair suggestions based on failures."""
    suggestions = []

    if guard_result.guard_type == "parse":
        suggestions.append("Syntax error introduced by edit")
        suggestions.append("Review the transformation logic for parse correctness")
    elif guard_result.guard_type == "ast-hash":
        suggestions.append("Semantic change detected (AST hash mismatch)")
        suggestions.append("Edit may have unintended side effects")
    elif guard_result.guard_type == "import-preservation":
        suggestions.append("Import statements were modified unexpectedly")
        suggestions.append("Check if transformation preserved necessary imports")

    if len(failed_indices) == 1:
        suggestions.append(f"Only edit #{failed_indices[0]} failed")
    else:
        suggestions.append(f"Edits {failed_indices} failed guard checks")

    suggestions.append("Manual review recommended before re-attempting")

    return suggestions


def _get_timestamp() -> str:
    """Get ISO 8601 timestamp."""
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def write_repair_report(report: RepairReport, repairs_dir: Path = Path(".ace/repairs")) -> Path:
    """
    Write repair report to disk.

    Args:
        report: RepairReport to write
        repairs_dir: Directory for repair reports

    Returns:
        Path to written report file
    """
    repairs_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename: {run_id}-{file_basename}.json
    file_basename = Path(report.file).name
    report_filename = f"{report.run_id}-{file_basename}.json"
    report_path = repairs_dir / report_filename

    # Write report
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")

    return report_path


def read_latest_repair_report(repairs_dir: Path = Path(".ace/repairs")) -> RepairReport | None:
    """
    Read the most recent repair report.

    Args:
        repairs_dir: Directory containing repair reports

    Returns:
        Most recent RepairReport or None if no reports exist
    """
    if not repairs_dir.exists():
        return None

    # Get all repair report files
    report_files = sorted(repairs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not report_files:
        return None

    # Read most recent report
    with open(report_files[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    return RepairReport.from_dict(data)
