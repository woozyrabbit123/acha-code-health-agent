"""
Pre-commit helper for ACHA Pro.

Scans only staged files and exits 1 on NEW HIGH severities.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

from acha.agents.analysis_agent import AnalysisAgent
from acha.baseline import compare_baseline


def get_staged_files(target_dir: str) -> list[str]:
    """
    Get list of staged Python files from git.

    Args:
        target_dir: Base directory for repository

    Returns:
        List of relative file paths for staged Python files
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        all_staged = result.stdout.strip().split("\n")
        # Filter for Python files
        py_files = [f for f in all_staged if f.endswith(".py") and f]
        return py_files
    except subprocess.CalledProcessError:
        print("Error: git diff failed. Not in a git repository?", file=sys.stderr)
        return []
    except FileNotFoundError:
        print("Error: git command not found", file=sys.stderr)
        return []


def run_precommit_scan(
    target_dir: str, baseline_path: str | None = None, staged_only: bool = True
) -> dict[str, Any]:
    """
    Run pre-commit scan on staged files.

    Args:
        target_dir: Target directory to scan
        baseline_path: Optional path to baseline.json for comparison
        staged_only: If True, only scan staged files (default: True)

    Returns:
        Dict with scan results and exit code
    """
    target_path = Path(target_dir).resolve()

    if not target_path.exists():
        return {"error": f"Target directory does not exist: {target_dir}", "exit_code": 1}

    # Get staged files
    if staged_only:
        staged_files = get_staged_files(str(target_path))
        if not staged_files:
            print("No Python files staged for commit")
            return {"findings": [], "new_high_severity": [], "exit_code": 0}

        print(f"Scanning {len(staged_files)} staged file(s)...")
        for f in staged_files:
            print(f"  - {f}")
    else:
        staged_files = None
        print(f"Scanning all files in {target_dir}...")

    # Run analysis
    agent = AnalysisAgent(parallel=False)

    if staged_files:
        # Analyze only staged files
        all_findings = []
        for file_path in staged_files:
            full_path = target_path / file_path
            if not full_path.exists():
                continue

            try:
                # Create temporary findings list for this file
                agent.findings = []
                agent._analyze_file(full_path, target_path)
                all_findings.extend(agent.findings)
            except Exception as e:
                print(f"Warning: Failed to analyze {file_path}: {e}", file=sys.stderr)

        result = {"findings": all_findings}
    else:
        # Analyze entire directory
        result = agent.run(str(target_path))

    findings = result.get("findings", [])

    # Compare against baseline if provided
    new_findings = findings
    if baseline_path and Path(baseline_path).exists():
        print(f"\nComparing against baseline: {baseline_path}")
        comparison = compare_baseline(findings, baseline_path)
        new_findings = comparison["new"]
        print(f"  New findings: {len(new_findings)}")
        print(f"  Existing findings: {len(comparison['existing'])}")
        print(f"  Fixed findings: {len(comparison['fixed'])}")

    # Check for new HIGH severity findings
    # Severity thresholds: critical >= 0.8, error >= 0.6, warning >= 0.3, info < 0.3
    high_severity_findings = []
    for finding in new_findings:
        severity = finding.get("severity", 0.0)
        if isinstance(severity, str):
            severity_map = {"critical": 0.9, "error": 0.7, "warning": 0.4, "info": 0.1}
            severity = severity_map.get(severity.lower(), 0.0)

        if severity >= 0.7:  # error or critical
            high_severity_findings.append(finding)

    # Print summary
    print("\nPre-commit scan results:")
    print(f"  Total findings: {len(findings)}")
    if baseline_path:
        print(f"  New findings: {len(new_findings)}")
    print(f"  High severity (error/critical): {len(high_severity_findings)}")

    if high_severity_findings:
        print("\nHigh severity findings:")
        for finding in high_severity_findings:
            file_path = finding.get("file", "unknown")
            line = finding.get("start_line", "?")
            rule = finding.get("rule", finding.get("finding", "unknown"))
            rationale = finding.get("rationale", "")
            print(f"  {file_path}:{line} [{rule}] {rationale}")

        print("\n❌ Commit blocked due to high severity findings")
        print("   Fix the issues above or use # acha: disable=RULE_NAME to suppress")
        return {
            "findings": findings,
            "new_findings": new_findings,
            "high_severity": high_severity_findings,
            "exit_code": 1,
        }
    else:
        print("\n✅ Pre-commit check passed")
        return {
            "findings": findings,
            "new_findings": new_findings,
            "high_severity": [],
            "exit_code": 0,
        }


def precommit_command(target_dir: str, baseline_path: str | None = None) -> int:
    """
    CLI entry point for pre-commit command.

    Args:
        target_dir: Target directory to scan
        baseline_path: Optional path to baseline.json

    Returns:
        Exit code (0 = success, 1 = high severity findings)
    """
    result = run_precommit_scan(target_dir, baseline_path, staged_only=True)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return result["exit_code"]

    return result["exit_code"]
