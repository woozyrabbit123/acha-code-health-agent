"""ACE deterministic summary generation for console and Markdown."""

from collections import defaultdict
from pathlib import Path

from ace.receipts import Receipt
from ace.uir import UnifiedIssue


def console_summary(findings: list[UnifiedIssue], receipts: list[Receipt]) -> None:
    """
    Print deterministic console summary of findings and receipts.

    Args:
        findings: List of findings
        receipts: List of apply receipts
    """
    if not findings and not receipts:
        print("✓ No issues found")
        return

    # Group findings by rule
    by_rule = defaultdict(list)
    for finding in findings:
        by_rule[finding.rule].append(finding)

    # Sort rules deterministically
    sorted_rules = sorted(by_rule.keys())

    print(f"\n{'='*60}")
    print(f"ACE Summary: {len(findings)} findings across {len(sorted_rules)} rules")
    print(f"{'='*60}\n")

    for rule_id in sorted_rules:
        rule_findings = by_rule[rule_id]
        print(f"{rule_id}: {len(rule_findings)} findings")

        # Show top 3 files for this rule
        files_by_count = defaultdict(int)
        for f in rule_findings:
            files_by_count[f.file] += 1

        top_files = sorted(files_by_count.items(), key=lambda x: (-x[1], x[0]))[:3]
        for file_path, count in top_files:
            print(f"  {file_path}: {count}")

    if receipts:
        print(f"\n{'='*60}")
        print(f"Applied {len(receipts)} fixes")
        print(f"{'='*60}\n")


def write_markdown_summary(
    findings: list[UnifiedIssue],
    receipts: list[Receipt],
    to: Path = Path(".ace/report.md"),
) -> None:
    """
    Write deterministic Markdown summary.

    Args:
        findings: List of findings
        receipts: List of apply receipts
        to: Output path (default: .ace/report.md)
    """
    # Group findings by rule
    by_rule = defaultdict(list)
    for finding in findings:
        by_rule[finding.rule].append(finding)

    # Sort rules deterministically
    sorted_rules = sorted(by_rule.keys())

    # Group findings by file
    by_file = defaultdict(int)
    for finding in findings:
        by_file[finding.file] += 1

    # Get top 10 files
    top_files = sorted(by_file.items(), key=lambda x: (-x[1], x[0]))[:10]

    lines = []
    lines.append("# ACE Analysis Report\n\n")

    # Summary
    lines.append("## Summary\n\n")
    lines.append(f"- **Total Findings**: {len(findings)}\n")
    lines.append(f"- **Rules Triggered**: {len(sorted_rules)}\n")
    lines.append(f"- **Files Affected**: {len(by_file)}\n")

    if receipts:
        lines.append(f"- **Fixes Applied**: {len(receipts)}\n")

    lines.append("\n")

    # Findings by rule
    lines.append("## Findings by Rule\n\n")

    for rule_id in sorted_rules:
        rule_findings = by_rule[rule_id]
        lines.append(f"### {rule_id} ({len(rule_findings)} findings)\n\n")

        # Sort findings by file, then line
        sorted_findings = sorted(rule_findings, key=lambda f: (f.file, f.line))

        for finding in sorted_findings[:20]:  # Limit to 20 per rule
            lines.append(
                f"- `{finding.file}:{finding.line}` - {finding.message}\n"
            )

        if len(rule_findings) > 20:
            lines.append(f"- ... and {len(rule_findings) - 20} more\n")

        lines.append("\n")

    # Top files
    if top_files:
        lines.append("## Top 10 Files by Issue Count\n\n")
        lines.append("| File | Issues |\n")
        lines.append("|------|--------|\n")

        for file_path, count in top_files:
            lines.append(f"| `{file_path}` | {count} |\n")

        lines.append("\n")

    # Write report
    to.parent.mkdir(parents=True, exist_ok=True)
    to.write_text("".join(lines), encoding="utf-8")
