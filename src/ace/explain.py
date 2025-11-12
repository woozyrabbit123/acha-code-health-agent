"""
Repair explanation module for ACE - pretty-prints repair reports.

Provides human-readable summaries of repair operations.
"""

from ace.repair import RepairReport


def explain_repair(report: RepairReport) -> str:
    """
    Generate human-readable explanation of a repair report.

    Args:
        report: RepairReport to explain

    Returns:
        Formatted multi-line string explaining the repair
    """
    lines = []
    lines.append("=" * 70)
    lines.append("ACE Repair Report")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"File: {report.file}")
    lines.append(f"Run ID: {report.run_id}")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append("")
    lines.append("Summary:")
    lines.append(f"  Total edits attempted: {report.total_edits}")
    lines.append(f"  ✓ Safe edits applied:   {report.safe_edits}")
    lines.append(f"  ✗ Failed edits skipped: {report.failed_edits}")
    lines.append("")

    if report.safe_edit_indices:
        lines.append(f"Applied edit indices: {report.safe_edit_indices}")
    if report.failed_edit_indices:
        lines.append(f"Skipped edit indices: {report.failed_edit_indices}")
    lines.append("")

    lines.append("Guard Failure Reason:")
    lines.append(f"  {report.guard_failure_reason}")
    lines.append("")

    if report.repair_suggestions:
        lines.append("Repair Suggestions:")
        for i, suggestion in enumerate(report.repair_suggestions, 1):
            lines.append(f"  {i}. {suggestion}")
        lines.append("")

    lines.append("Next Steps:")
    if report.safe_edits > 0:
        lines.append("  • Safe edits have been applied to your workspace")
        lines.append("  • Review the changes and test your code")
    lines.append("  • Manually review the failed edits before re-attempting")
    lines.append("  • Consider filing a bug report if the guard failure seems incorrect")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_repair_summary(report: RepairReport) -> str:
    """
    Generate a short one-line summary of a repair.

    Args:
        report: RepairReport to summarize

    Returns:
        One-line summary string
    """
    status = f"{report.safe_edits}/{report.total_edits} edits applied"
    file_name = report.file.split("/")[-1] if "/" in report.file else report.file
    return f"⚠️  Partial repair: {status} in {file_name}"
