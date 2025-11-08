"""
Baseline system for ACHA Pro.

Allows tracking known issues and detecting only NEW/CHANGED findings.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


def _generate_finding_id(finding: dict[str, Any]) -> str:
    """
    Generate stable, deterministic ID for a finding.

    Based on: file path, line, rule type, and a hash of the message.
    This allows tracking the same issue across runs.
    """
    key_parts = [
        finding.get("file", ""),
        str(finding.get("start_line", 0)),
        str(finding.get("end_line", 0)),
        finding.get("finding", ""),
        finding.get("rationale", "")[:100],  # First 100 chars to reduce noise
    ]

    key_str = "|".join(key_parts)
    hash_hex = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]

    return f"{finding.get('finding', 'UNK')}:{finding.get('file', 'unknown')}:{finding.get('start_line', 0)}:{hash_hex}"


def create_baseline(findings: list[dict[str, Any]], output_path: str) -> dict[str, Any]:
    """
    Create baseline file from current findings.

    Args:
        findings: List of findings from analysis
        output_path: Where to write baseline.json

    Returns:
        Baseline data structure
    """
    baseline = {
        "version": "1.0",
        "created_at": "",  # Would use datetime.now().isoformat()
        "findings": {},
    }

    for finding in findings:
        finding_id = _generate_finding_id(finding)
        baseline["findings"][finding_id] = {
            "file": finding.get("file"),
            "line": finding.get("start_line"),
            "rule": finding.get("finding"),
            "severity": finding.get("severity"),
        }

    # Write to file
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, sort_keys=True)

    return baseline


def compare_baseline(
    current_findings: list[dict[str, Any]], baseline_path: str
) -> dict[str, Any]:
    """
    Compare current findings against baseline.

    Args:
        current_findings: Current analysis findings
        baseline_path: Path to baseline.json

    Returns:
        Dict with 'new', 'fixed', 'existing' lists
    """
    # Load baseline
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    baseline_ids = set(baseline.get("findings", {}).keys())
    current_ids = {_generate_finding_id(f): f for f in current_findings}

    new_findings = []
    existing_findings = []

    for finding_id, finding in current_ids.items():
        if finding_id in baseline_ids:
            existing_findings.append(finding)
        else:
            new_findings.append(finding)

    fixed_ids = baseline_ids - set(current_ids.keys())

    return {
        "new": new_findings,
        "existing": existing_findings,
        "fixed": list(fixed_ids),
        "summary": {
            "new_count": len(new_findings),
            "existing_count": len(existing_findings),
            "fixed_count": len(fixed_ids),
        },
    }
