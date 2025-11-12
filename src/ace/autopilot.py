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
from ace.learn import LearningEngine, context_key, get_rule_ids_from_plan
from ace.policy import PolicyEngine
from ace.receipts import Receipt
from ace.skiplist import Skiplist
from ace.telemetry import get_cost_ms_rank
from ace.uir import UnifiedIssue

# v1.5: Context engine imports
try:
    from ace.repomap import RepoMap
    from ace.context_rank import ContextRanker
    from ace.depgraph import DepGraph
    from ace.impact import ImpactAnalyzer
    CONTEXT_ENGINE_AVAILABLE = True
except ImportError:
    CONTEXT_ENGINE_AVAILABLE = False


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
    deep: bool = False  # Disable clean-skip heuristic


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

        # Initialize learning engine
        learning = LearningEngine()
        learning.load()

        # Initialize content index for incremental analysis
        index = ContentIndex()
        if cfg.incremental:
            index.load()

        # v1.5: Load context engine (RepoMap) if available
        repo_map = None
        context_ranker = None
        depgraph = None
        impact_analyzer = None

        symbols_path = Path(".ace/symbols.json")
        if CONTEXT_ENGINE_AVAILABLE:
            # Load or build if --deep and symbols are stale (>24h)
            should_rebuild = False
            if cfg.deep and symbols_path.exists():
                import time
                symbols_age = time.time() - symbols_path.stat().st_mtime
                if symbols_age > 86400:  # 24 hours
                    should_rebuild = True

            if should_rebuild or (cfg.deep and not symbols_path.exists()):
                if not cfg.silent:
                    print("Building symbol index (--deep mode)...")
                repo_map = RepoMap().build(cfg.target if cfg.target.is_dir() else cfg.target.parent)
                repo_map.save(symbols_path)
            elif symbols_path.exists():
                if not cfg.silent:
                    print("RepoMap loaded")
                repo_map = RepoMap.load(symbols_path)

            # Initialize context engine components if repo_map is available
            if repo_map:
                context_ranker = ContextRanker(repo_map)
                depgraph = DepGraph(repo_map)
                impact_analyzer = ImpactAnalyzer(depgraph)

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
            deep=cfg.deep,
        )

        stats.findings_count = len(findings)

        if not findings:
            if not cfg.silent:
                print("✓ No issues found")
            return (ExitCode.SUCCESS, stats)

        # Step 5: Apply skiplist filtering
        findings = skiplist.filter_findings(findings)

        # v1.7: Apply auto-skiplist from learning
        filtered_findings = []
        for finding in findings:
            should_skip = learning.should_skip_file_for_rule(finding.rule, finding.file)
            if not should_skip:
                filtered_findings.append(finding)
        findings = filtered_findings

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

            # Get tuned thresholds from learning for this plan's rules
            # Use the first rule's tuned thresholds (if plan has multiple rules, they likely have similar thresholds)
            rule_ids = get_rule_ids_from_plan(plan)
            if rule_ids:
                tuned_auto, tuned_suggest = learning.tuned_thresholds(rule_ids[0])
            else:
                tuned_auto, tuned_suggest = (policy.auto_threshold, policy.suggest_threshold)

            # Apply policy threshold
            if cfg.allow_mode == "auto":
                # Auto mode: approve if R* >= tuned auto threshold
                if risk_score >= tuned_auto:
                    approved_plans.append(plan)
                else:
                    stats.policy_denied += 1
                    # Learning: Record as skipped (failed policy threshold)
                    ctx_key = context_key(plan)
                    for rule_id in rule_ids:
                        learning.record_outcome(rule_id, "skipped", ctx_key)
            elif cfg.allow_mode == "suggest":
                # Suggest mode: approve if R* >= tuned suggest threshold
                if risk_score >= tuned_suggest:
                    approved_plans.append(plan)
                    # Learning: Record as suggested (approved but not auto-applied)
                    ctx_key = context_key(plan)
                    for rule_id in rule_ids:
                        learning.record_outcome(rule_id, "suggested", ctx_key)
                else:
                    stats.policy_denied += 1
                    # Learning: Record as skipped (failed policy threshold)
                    ctx_key = context_key(plan)
                    for rule_id in rule_ids:
                        learning.record_outcome(rule_id, "skipped", ctx_key)

        stats.plans_approved = len(approved_plans)

        if not approved_plans:
            if not cfg.silent:
                print(f"✓ No plans approved by policy (denied: {stats.policy_denied})")
            return (ExitCode.SUCCESS, stats)

        # Step 8: Sort plans by priority using smart prioritization
        # priority = (R★ * 100) - cost_ms_rank - revisit_penalty

        # Get all unique rule IDs from approved plans
        all_rule_ids = []
        for plan in approved_plans:
            all_rule_ids.extend(get_rule_ids_from_plan(plan))
        all_rule_ids = list(set(all_rule_ids))

        # Get cost ranking from telemetry
        cost_ranks = get_cost_ms_rank(all_rule_ids)

        # Calculate priority for each plan
        def calculate_priority(plan):
            rule_ids = get_rule_ids_from_plan(plan)

            # Base priority from risk score
            base_priority = plan.estimated_risk * 100

            # Cost penalty (average rank of rules in plan)
            cost_penalty = 0.0
            if rule_ids:
                cost_penalty = sum(cost_ranks.get(rid, 0) for rid in rule_ids) / len(rule_ids)

            # Revisit penalty (check if context was reverted recently)
            revisit_penalty = 0.0
            ctx_key = context_key(plan)
            if learning.should_skip_context(ctx_key, threshold=0.5):
                revisit_penalty = 20.0  # Significant penalty for previously reverted contexts

            # v1.5: Context ranking boost
            context_boost = 0.0
            if context_ranker and hasattr(plan, 'edits') and plan.edits:
                # Get files affected by this plan
                affected_files = list(set(edit.file_path for edit in plan.edits))

                # Score each file
                total_score = 0.0
                for file_path in affected_files:
                    # Try to get relative path
                    try:
                        rel_path = str(Path(file_path).relative_to(cfg.target))
                    except ValueError:
                        rel_path = str(file_path)

                    # Get file symbols and calculate density/recency
                    file_symbols = repo_map.get_file_symbols(rel_path)
                    if file_symbols:
                        # Use ranker's scoring components
                        file_score = context_ranker._score_file(
                            rel_path,
                            query=None,
                            recency_weight=0.3,
                            density_weight=0.5,
                            relevance_weight=0.0
                        )
                        if file_score:
                            total_score += file_score.score

                # Average boost across files (weight 0.2 to avoid dominating)
                if affected_files:
                    context_boost = (total_score / len(affected_files)) * 5.0  # Scale up to ~5 points max

            # v1.7: Success rate bonus (prefer high-success rules)
            success_rate_bonus = 0.0
            if rule_ids:
                success_rates = []
                for rule_id in rule_ids:
                    if rule_id in learning.data.rules:
                        stats_obj = learning.data.rules[rule_id]
                        if stats_obj.sample_size() >= 5:  # Only consider rules with enough samples
                            success_rates.append(stats_obj.success_rate())

                if success_rates:
                    avg_success_rate = sum(success_rates) / len(success_rates)
                    success_rate_bonus = avg_success_rate * 10.0  # Scale to ~10 points max

            priority = base_priority - cost_penalty - revisit_penalty + context_boost + success_rate_bonus

            return priority

        # Sort by priority descending, then by plan ID for determinism
        approved_plans.sort(key=lambda p: (-calculate_priority(p), p.id))

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

        # v1.7: Record applied outcomes in learning (with file_path for auto-skiplist)
        for receipt in receipts:
            # Extract rule_id from receipt metadata
            rule_id = receipt.metadata.get("rule_id") if hasattr(receipt, "metadata") and isinstance(receipt.metadata, dict) else None
            if not rule_id and hasattr(receipt, "rule"):
                rule_id = receipt.rule
            if rule_id:
                learning.record_outcome(rule_id, "applied", context_key=None, file_path=receipt.file)

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
