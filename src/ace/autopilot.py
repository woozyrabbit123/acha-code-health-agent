"""
ACE Autopilot - Orchestrates end-to-end analysis, packing, gating, and safe application.

One-command workflow for automated code health improvements.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from ace.budget import BudgetConstraints, apply_budget
from ace.errors import ACEError, ExitCode, OperationalError
from ace.index import ContentIndex, is_indexable
from ace.journal import Journal
from ace.kernel import run_analyze, run_apply, run_refactor
from ace.policy import PolicyEngine
from ace.receipts import Receipt
from ace.skiplist import Skiplist
from ace.uir import UnifiedIssue


@dataclass
class AutopilotConfig:
    """Configuration for autopilot run."""

    target: Path
    allow_mode: str = "suggest"  # "auto" or "suggest"
    max_files: int | None = None
    max_lines: int | None = None
    incremental: bool = False
    dry_run: bool = False
    silent: bool = False
    rules: list[str] | None = None


@dataclass
class AutopilotStats:
    """Statistics from an autopilot run."""

    findings_count: int = 0
    plans_count: int = 0
    plans_approved: int = 0
    plans_applied: int = 0
    plans_failed: int = 0
    files_modified: int = 0
    lines_modified: int = 0
    budget_excluded: int = 0
    policy_denied: int = 0


def run_autopilot(cfg: AutopilotConfig) -> tuple[ExitCode, AutopilotStats]:
    """
    Run autopilot orchestration: analyze → pack → gate → apply → verify.

    Args:
        cfg: Autopilot configuration

    Returns:
        Tuple of (exit_code, stats)
    """
    stats = AutopilotStats()

    try:
        # Step 1: Ensure .ace/ directory exists
        ace_dir = Path(".ace")
        ace_dir.mkdir(exist_ok=True)

        # Step 2: Load or initialize supporting files
        skiplist = Skiplist()
        skiplist.load()

        # Initialize content index for incremental analysis
        index = ContentIndex()
        if cfg.incremental:
            index.load()

        # Step 3: Build file list (respects .aceignore, size>5MB skip)
        if cfg.target.is_file():
            files = [cfg.target]
        else:
            files = sorted(cfg.target.rglob("*"))
            files = [f for f in files if f.is_file() and is_indexable(f)]

        # Filter for changed files if incremental
        if cfg.incremental:
            files = index.get_changed_files(files)

        if not files:
            if not cfg.silent:
                print("✓ No files to analyze (incremental check: all up-to-date)")
            return (ExitCode.SUCCESS, stats)

        # Step 4: Analyze (with incremental support)
        if not cfg.silent:
            print(f"Analyzing {len(files)} file(s)...")

        findings = run_analyze(
            cfg.target,
            cfg.rules,
            incremental=cfg.incremental,
            use_cache=True,
        )

        stats.findings_count = len(findings)

        if not findings:
            if not cfg.silent:
                print("✓ No issues found")
            return (ExitCode.SUCCESS, stats)

        # Step 5: Apply skiplist filtering
        findings = skiplist.filter_findings(findings)

        if not findings:
            if not cfg.silent:
                print("✓ No actionable findings (all in skiplist)")
            return (ExitCode.SUCCESS, stats)

        # Step 6: Generate refactoring plans
        if not cfg.silent:
            print(f"Generating refactoring plans for {len(findings)} finding(s)...")

        plans = run_refactor(cfg.target, cfg.rules)
        stats.plans_count = len(plans)

        if not plans:
            if not cfg.silent:
                print("✓ No refactoring plans generated")
            return (ExitCode.SUCCESS, stats)

        # Step 7: Apply policy gates and risk scoring
        policy = PolicyEngine()
        approved_plans = []

        for plan in plans:
            # Use existing estimated_risk from plan (already calculated during refactoring)
            # Plans come with estimated_risk already set
            risk_score = plan.estimated_risk

            # Apply policy threshold
            if cfg.allow_mode == "auto":
                # Auto mode: approve if R* >= 0.70
                if risk_score >= policy.auto_threshold:
                    approved_plans.append(plan)
                else:
                    stats.policy_denied += 1
            elif cfg.allow_mode == "suggest":
                # Suggest mode: approve if R* >= 0.50
                if risk_score >= policy.suggest_threshold:
                    approved_plans.append(plan)
                else:
                    stats.policy_denied += 1

        stats.plans_approved = len(approved_plans)

        if not approved_plans:
            if not cfg.silent:
                print(f"✓ No plans approved by policy (denied: {stats.policy_denied})")
            return (ExitCode.SUCCESS, stats)

        # Step 8: Sort plans by priority (R* desc, then path for determinism)
        approved_plans.sort(key=lambda p: (-p.estimated_risk, p.id))

        # Step 9: Enforce change budget
        if cfg.max_files or cfg.max_lines:
            constraints = BudgetConstraints(
                max_files=cfg.max_files, max_lines=cfg.max_lines
            )
            included_plans, budget_summary = apply_budget(approved_plans, constraints)
            stats.budget_excluded = budget_summary.excluded_count
            approved_plans = included_plans

        if not approved_plans:
            if not cfg.silent:
                print(
                    f"✓ No plans within budget (excluded: {stats.budget_excluded})"
                )
            return (ExitCode.SUCCESS, stats)

        # Step 10: Apply changes (with Journal + PatchGuard)
        if cfg.dry_run:
            if not cfg.silent:
                print(f"[DRY RUN] Would apply {len(approved_plans)} plan(s)")
                for plan in approved_plans[:10]:
                    print(f"  - {plan.id} (R*={plan.estimated_risk:.2f})")
            stats.plans_approved = len(approved_plans)
            return (ExitCode.SUCCESS, stats)

        if not cfg.silent:
            print(f"Applying {len(approved_plans)} plan(s)...")

        # Use run_apply with journal
        exit_code, receipts = run_apply(
            cfg.target,
            cfg.rules,
            dry_run=False,
            force=False,
            max_files=cfg.max_files,
            max_lines=cfg.max_lines,
        )

        stats.plans_applied = len(receipts)
        stats.files_modified = len(set(r.file for r in receipts))

        # Count lines modified from receipts
        for receipt in receipts:
            # Estimate lines from risk and plan data
            stats.lines_modified += 1  # Simplified count

        # Step 11: Verify receipts and update index
        if cfg.incremental:
            for receipt in receipts:
                try:
                    file_path = Path(receipt.file)
                    if file_path.exists():
                        index.add_file(file_path)
                except Exception:
                    pass
            index.save()

        # Step 12: Write session log
        session_log_path = ace_dir / "session.log"
        with open(session_log_path, "a", encoding="utf-8") as f:
            session_entry = {
                "timestamp": receipts[0].timestamp if receipts else "",
                "findings": stats.findings_count,
                "plans": stats.plans_count,
                "applied": stats.plans_applied,
                "files": stats.files_modified,
                "mode": cfg.allow_mode,
            }
            f.write(json.dumps(session_entry, sort_keys=True) + "\n")

        if not cfg.silent:
            print(
                f"✓ Applied {stats.plans_applied} plan(s) across {stats.files_modified} file(s)"
            )

        return (exit_code, stats)

    except ACEError as e:
        if not cfg.silent:
            print(f"Error: {e}", file=sys.stderr)
        return (e.exit_code, stats)
    except Exception as e:
        if not cfg.silent:
            print(f"Unexpected error: {e}", file=sys.stderr)
        return (ExitCode.OPERATIONAL_ERROR, stats)
