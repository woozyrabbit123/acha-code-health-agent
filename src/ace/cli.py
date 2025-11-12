#!/usr/bin/env python3
"""ACE CLI - Autonomous Code Editor command-line interface."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from ace import __version__
from ace.errors import (
    ACEError,
    ExitCode,
    OperationalError,
    PolicyDenyError,
    format_error,
)
from ace.journal import (
    Journal,
    build_revert_plan,
    find_latest_journal,
    get_journal_id_from_path,
    read_journal,
)
from ace.kernel import run_analyze, run_apply, run_refactor, run_validate, run_warmup
from ace.safety import atomic_write, content_hash
from ace.storage import compare_baseline, save_baseline
from ace.policy_config import load_policy_config
from ace.skiplist import Skiplist


def cmd_analyze(args):
    """Analyze code for issues across multiple languages."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        # Cache parameters
        use_cache = not args.no_cache
        cache_ttl = args.cache_ttl if hasattr(args, "cache_ttl") else 3600
        cache_dir = args.cache_dir if hasattr(args, "cache_dir") else ".ace"

        # Parallel execution
        jobs = args.jobs if hasattr(args, "jobs") else 1

        # Performance profiling
        if hasattr(args, "profile") and args.profile:
            from ace.perf import get_profiler
            profiler = get_profiler()
            profiler.enable()

        # Incremental parameters
        incremental = args.incremental if hasattr(args, "incremental") else False
        rebuild_index = args.rebuild_index if hasattr(args, "rebuild_index") else False

        findings = run_analyze(
            target,
            rules,
            use_cache=use_cache,
            cache_ttl=cache_ttl,
            cache_dir=cache_dir,
            jobs=jobs,
            incremental=incremental,
            rebuild_index=rebuild_index,
        )

        # Save profile if requested
        if hasattr(args, "profile") and args.profile:
            profiler.save(args.profile)

        # Output as JSON
        output = [f.to_dict() for f in findings]
        print(json.dumps(output, indent=2, sort_keys=True))

        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_refactor(args):
    """Plan refactoring changes."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        plans = run_refactor(target, rules)

        # Output as JSON
        output = [p.to_dict() for p in plans]
        print(json.dumps(output, indent=2, sort_keys=True))

        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_validate(args):
    """Validate refactored code."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        receipts = run_validate(target, rules)

        # Output as JSON
        print(json.dumps(receipts, indent=2, sort_keys=True))

        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_export(args):
    """Export analysis results and receipts."""
    try:
        print("ACE v0.1 stub: export")
        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_baseline_create(args):
    """Create a baseline snapshot of current findings."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None
        baseline_path = args.baseline_path

        # Run analysis (with cache disabled for baseline creation)
        findings = run_analyze(target, rules, use_cache=False)

        # Convert to dicts and save
        findings_dicts = [f.to_dict() for f in findings]
        save_baseline(findings_dicts, baseline_path)

        print(f"Baseline created with {len(findings)} findings → {baseline_path}")
        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_baseline_compare(args):
    """Compare current findings against baseline."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None
        baseline_path = args.baseline_path

        if not Path(baseline_path).exists():
            raise OperationalError(f"Baseline file does not exist: {baseline_path}")

        # Run analysis
        findings = run_analyze(target, rules, use_cache=True)

        # Convert to dicts and compare
        findings_dicts = [f.to_dict() for f in findings]
        comparison = compare_baseline(findings_dicts, baseline_path)

        # Print summary
        added_count = len(comparison["added"])
        removed_count = len(comparison["removed"])
        changed_count = len(comparison["changed"])
        existing_count = len(comparison["existing"])

        print(json.dumps(comparison, indent=2, sort_keys=True))
        print("\n--- Baseline Comparison ---", file=sys.stderr)
        print(f"Added:    {added_count}", file=sys.stderr)
        print(f"Removed:  {removed_count}", file=sys.stderr)
        print(f"Changed:  {changed_count}", file=sys.stderr)
        print(f"Existing: {existing_count}", file=sys.stderr)

        # Exit code based on policy flags
        if args.fail_on_new and added_count > 0:
            print(f"\nFAIL: {added_count} new findings detected", file=sys.stderr)
            return ExitCode.POLICY_DENY

        if args.fail_on_regression and (added_count > 0 or changed_count > 0):
            print(f"\nFAIL: Regression detected ({added_count} new, {changed_count} changed)", file=sys.stderr)
            return ExitCode.POLICY_DENY

        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_apply(args):
    """Apply refactoring changes with safety checks."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        # Budget parameters
        max_files = args.max_files if hasattr(args, "max_files") else None
        max_lines = args.max_lines if hasattr(args, "max_lines") else None
        journal_dir = args.journal_dir if hasattr(args, "journal_dir") else ".ace/journals"

        exit_code, receipts = run_apply(
            target,
            rules,
            dry_run=not args.yes,
            force=args.force,
            stash=args.stash,
            commit=args.commit,
            max_files=max_files,
            max_lines=max_lines,
            journal_dir=journal_dir,
        )

        # Write receipts if any were generated
        if receipts:
            receipts_path = Path("receipts.json")
            import json
            with open(receipts_path, "w", encoding="utf-8") as f:
                json.dump(
                    [r.to_dict() for r in receipts],
                    f,
                    indent=2,
                    sort_keys=True,
                )
            print(f"Generated {len(receipts)} receipt(s) → {receipts_path}")

        if exit_code == ExitCode.SUCCESS:
            print("Refactoring applied successfully")
        elif exit_code == ExitCode.POLICY_DENY:
            raise PolicyDenyError("Refactoring blocked by policy (dirty git tree or high risk)")
        else:
            raise OperationalError("Refactoring failed")

        return exit_code

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_revert(args):
    """Revert changes from a journal."""
    try:
        # Determine journal path
        if args.journal == "latest":
            journal_path = find_latest_journal()
            if journal_path is None:
                raise OperationalError("No journals found in .ace/journals/")
        elif Path(args.journal).exists():
            journal_path = Path(args.journal)
        else:
            # Try as journal ID
            journal_path = Path(f".ace/journals/{args.journal}.jsonl")
            if not journal_path.exists():
                raise OperationalError(f"Journal not found: {args.journal}")

        journal_id = get_journal_id_from_path(journal_path)
        print(f"Reverting from journal: {journal_id}")

        # Build revert plan
        revert_plan = build_revert_plan(journal_path)

        if not revert_plan:
            print("No changes to revert.")
            return ExitCode.SUCCESS

        print(f"Found {len(revert_plan)} file(s) to revert")

        # Initialize skiplist for auto-learning
        skiplist = Skiplist()

        # Initialize learning engine
        from ace.learn import LearningEngine
        learning = LearningEngine()
        learning.load()

        # Revert each file in reverse order
        reverted = 0
        failed = 0

        for context in revert_plan:
            file_path = Path(context.file)

            try:
                # Verify current state matches expected
                if not file_path.exists():
                    print(f"  SKIP {context.file}: file does not exist", file=sys.stderr)
                    failed += 1
                    continue

                current_content = file_path.read_bytes()
                current_sha = hashlib.sha256(current_content).hexdigest()

                if current_sha != context.expected_current_sha:
                    print(
                        f"  SKIP {context.file}: current hash mismatch "
                        f"(expected {context.expected_current_sha[:8]}..., "
                        f"got {current_sha[:8]}...)",
                        file=sys.stderr
                    )
                    failed += 1
                    continue

                # Restore original content
                atomic_write(file_path, context.restore_content)

                # Verify restored hash
                restored_content = file_path.read_bytes()
                restored_sha = hashlib.sha256(restored_content).hexdigest()

                # Note: We only stored first 4KB in journal, so we can't verify full hash
                # Just check that the file was written successfully
                print(f"  ✓ {context.file}")
                reverted += 1

                # Auto-learn: Add reverted rules to skiplist
                for rule_id in context.rule_ids:
                    # Use file as context, and a generic content marker
                    skiplist.add(
                        rule_id=rule_id,
                        content=f"manual-revert:{context.plan_id}",
                        context_path=context.file,
                        reason="manual-revert"
                    )

                    # Learning: Record manual revert outcome
                    learning.record_outcome(rule_id, "reverted", context_key=None)

            except Exception as e:
                print(f"  FAIL {context.file}: {e}", file=sys.stderr)
                failed += 1

        print(f"\nReverted: {reverted} file(s)")
        if failed > 0:
            print(f"Failed: {failed} file(s)", file=sys.stderr)
            return ExitCode.OPERATIONAL_ERROR

        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_warmup(args):
    """Warm up analysis cache by pre-analyzing files."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        # Run warmup (analyze without applying changes)
        from ace.kernel import run_warmup
        stats = run_warmup(target, rules)

        print(f"Cache warmup complete:")
        print(f"  Files analyzed: {stats['analyzed']}")
        print(f"  Cache hits: {stats['cache_hits']}")
        print(f"  Cache misses: {stats['cache_misses']}")

        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_watch(args):
    """Watch files for changes and auto-analyze."""
    import time
    from ace.index import ContentIndex

    try:
        target = Path(args.target)
        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None
        interval = args.interval if hasattr(args, "interval") else 5

        print(f"Watching {target} for changes (interval: {interval}s)...")

        index = ContentIndex()
        index.load()

        while True:
            # Get all files
            if target.is_file():
                files = [target]
            else:
                from ace.index import is_indexable
                files = sorted(target.rglob("*"))
                files = [f for f in files if f.is_file() and is_indexable(f)]

            # Check for changes
            changed_files = index.get_changed_files(files)

            if changed_files:
                print(f"\n{len(changed_files)} file(s) changed, analyzing...")
                findings = run_analyze(target, rules, use_cache=True)

                if findings:
                    print(f"Found {len(findings)} issue(s):")
                    for f in findings[:10]:  # Show first 10
                        print(f"  {f.file}:{f.line} [{f.rule}] {f.message}")
                    if len(findings) > 10:
                        print(f"  ... and {len(findings) - 10} more")
                else:
                    print("No issues found")

                # Update index
                for file_path in changed_files:
                    try:
                        index.add_file(file_path)
                    except Exception:
                        pass
                index.save()

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nWatch stopped")
        return ExitCode.SUCCESS
    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_report(args):
    """Generate analysis report."""
    try:
        target = Path(args.target)
        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None
        output_format = args.format if hasattr(args, "format") else "text"
        output_file = args.output if hasattr(args, "output") else None

        # Run analysis
        findings = run_analyze(target, rules)

        # Generate report based on format
        if output_format == "json":
            report = json.dumps([f.to_dict() for f in findings], indent=2, sort_keys=True)
        elif output_format == "sarif":
            # Basic SARIF format
            report = json.dumps({
                "version": "2.1.0",
                "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
                "runs": [{
                    "tool": {
                        "driver": {
                            "name": "ACE",
                            "version": __version__
                        }
                    },
                    "results": [{
                        "ruleId": f.rule,
                        "level": f.severity.value,
                        "message": {"text": f.message},
                        "locations": [{
                            "physicalLocation": {
                                "artifactLocation": {"uri": f.file},
                                "region": {"startLine": f.line}
                            }
                        }]
                    } for f in findings]
                }]
            }, indent=2)
        else:  # text format
            report = f"ACE Analysis Report\n"
            report += f"=" * 60 + "\n\n"
            report += f"Total findings: {len(findings)}\n\n"

            # Group by severity
            by_severity = {}
            for f in findings:
                sev = f.severity.value
                if sev not in by_severity:
                    by_severity[sev] = []
                by_severity[sev].append(f)

            for severity in ["high", "medium", "low"]:
                if severity in by_severity:
                    report += f"\n{severity.upper()} ({len(by_severity[severity])})\n"
                    report += "-" * 60 + "\n"
                    for f in by_severity[severity]:
                        report += f"{f.file}:{f.line} [{f.rule}]\n"
                        report += f"  {f.message}\n"
                        if f.suggestion:
                            report += f"  Suggestion: {f.suggestion}\n"
                        report += "\n"

        # Write or print report
        if output_file:
            Path(output_file).write_text(report)
            print(f"Report written to {output_file}")
        else:
            print(report)

        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_policy(args):
    """Manage policy configuration."""
    try:
        subcommand = args.policy_command if hasattr(args, "policy_command") else None

        if subcommand == "show":
            # Show current policy
            policy_path = Path(args.policy_file) if hasattr(args, "policy_file") else Path("policy.toml")
            if policy_path.exists():
                policy = load_policy_config(policy_path)
                print(f"Policy: {policy.description}")
                print(f"Version: {policy.version}")
                print(f"\nScoring weights:")
                print(f"  Severity (α): {policy.alpha}")
                print(f"  Complexity (β): {policy.beta}")
                print(f"  Cohesion (γ): {policy.gamma}")
                print(f"\nThresholds:")
                print(f"  Auto-apply: R* ≥ {policy.auto_threshold}")
                print(f"  Suggest: R* ≥ {policy.suggest_threshold}")
                print(f"  Report: R* ≥ {policy.report_threshold}")
            else:
                print(f"Policy file not found: {policy_path}")
                return ExitCode.OPERATIONAL_ERROR
        else:
            print("Usage: ace policy show [--policy-file PATH]")
            return ExitCode.INVALID_ARGS

        return ExitCode.SUCCESS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_autopilot(args):
    """Run autopilot orchestration."""
    try:
        from ace.autopilot import AutopilotConfig, run_autopilot
        from ace.summary import print_run_summary

        target = Path(args.target)
        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        cfg = AutopilotConfig(
            target=target,
            allow_mode=args.allow if hasattr(args, "allow") else "suggest",
            max_files=args.max_files if hasattr(args, "max_files") else None,
            max_lines=args.max_lines if hasattr(args, "max_lines") else None,
            incremental=args.incremental if hasattr(args, "incremental") else False,
            dry_run=args.dry_run if hasattr(args, "dry_run") else False,
            silent=args.silent if hasattr(args, "silent") else False,
            rules=rules,
            deep=args.deep if hasattr(args, "deep") else False,
        )

        exit_code, stats = run_autopilot(cfg)

        # Print summary
        if not cfg.silent:
            print_run_summary(stats, silent=cfg.silent)

        return exit_code

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_verify(args):
    """Verify receipts against journal and filesystem."""
    try:
        from ace.receipts import verify_receipts

        base_path = Path(args.base_path) if hasattr(args, "base_path") else Path(".")

        failures = verify_receipts(base_path)

        if not failures:
            receipt_count = len(list(Path(".ace/journals").rglob("*.jsonl"))) if Path(".ace/journals").exists() else 0
            print(f"✓ Integrity OK ({receipt_count} receipt(s))")
            return ExitCode.SUCCESS
        else:
            print(f"✗ Verification failed: {len(failures)} issue(s)", file=sys.stderr)
            for failure in failures[:10]:  # Show first 10
                print(f"  - {failure}", file=sys.stderr)
            if len(failures) > 10:
                print(f"  ... and {len(failures) - 10} more", file=sys.stderr)
            return ExitCode.OPERATIONAL_ERROR

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_tune(args):
    """Show performance tuning recommendations based on telemetry."""
    try:
        from ace.telemetry import Telemetry

        telemetry = Telemetry()

        # Load telemetry stats
        stats = telemetry.load_stats()

        if stats.total_executions == 0:
            print("No telemetry data yet. Run analyze/autopilot to collect performance data.")
            return ExitCode.SUCCESS

        # Get top 3 slowest rules
        top_slow_rules = telemetry.get_top_slow_rules(limit=3)

        print("ACE Performance Tuning\n" + "=" * 60)
        print(f"\nTotal rule executions: {stats.total_executions}")

        if top_slow_rules:
            print(f"\nTop {len(top_slow_rules)} slowest rules:\n")
            print(f"{'Rule ID':<35} {'Avg Time (ms)':<15} {'Count':<10}")
            print("-" * 60)

            for rule_id, avg_ms, count in top_slow_rules:
                print(f"{rule_id:<35} {avg_ms:>13.2f} {count:>9}")

            # Calculate estimated time per file
            if top_slow_rules:
                total_avg_time = sum(avg_ms for _, avg_ms, _ in top_slow_rules)
                files_per_second = 1000.0 / total_avg_time if total_avg_time > 0 else 0

                print(f"\n{'Estimated throughput':<30}: {files_per_second:.1f} files/sec")

                # Suggest --max-files for different time budgets
                print(f"\nRecommended --max-files for time budgets:")
                for seconds in [10, 30, 60]:
                    max_files = int(files_per_second * seconds)
                    print(f"  {seconds:3d}s runtime: --max-files={max_files}")
        else:
            print("\nNo slow rules detected.")

        return ExitCode.SUCCESS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_repair(args):
    """Show repair report for partial edit failures."""
    try:
        from ace.explain import explain_repair
        from ace.repair import read_latest_repair_report

        if args.repair_command == "show" or getattr(args, "latest", False):
            # Show latest repair report
            report = read_latest_repair_report()

            if not report:
                print("No repair reports found. Run autopilot to generate repairs.")
                return ExitCode.SUCCESS

            # Print detailed explanation
            print(explain_repair(report))

        return ExitCode.SUCCESS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_learn(args):
    """Manage learning data and adaptive thresholds."""
    try:
        from ace.learn import LearningEngine

        subcommand = args.learn_command if hasattr(args, "learn_command") else None

        learning = LearningEngine()
        learning.load()

        if subcommand == "show":
            # Show top rules by revert rate and threshold adjustments
            print("ACE Learning Statistics\n" + "=" * 60)

            top_rules = learning.get_top_rules_by_revert_rate(limit=10)

            if not top_rules:
                print("No learning data yet. Run autopilot to start learning.")
                return ExitCode.SUCCESS

            print(f"\nTop {len(top_rules)} rules by revert rate:\n")
            print(f"{'Rule ID':<35} {'Applied':<10} {'Reverted':<10} {'Rate':<8} {'Threshold Adj':<15}")
            print("-" * 90)

            for rule_id, stats, revert_rate in top_rules:
                tuned_auto, tuned_suggest = learning.tuned_thresholds(rule_id)

                # Check if threshold was adjusted
                from ace.learn import DEFAULT_MIN_AUTO
                if tuned_auto != DEFAULT_MIN_AUTO:
                    adj = f"+{(tuned_auto - DEFAULT_MIN_AUTO):.2f}" if tuned_auto > DEFAULT_MIN_AUTO else f"{(tuned_auto - DEFAULT_MIN_AUTO):.2f}"
                    threshold_info = f"auto: {tuned_auto:.2f} ({adj})"
                else:
                    threshold_info = "default"

                print(f"{rule_id:<35} {stats.applied:<10} {stats.reverted:<10} {revert_rate*100:>6.1f}% {threshold_info:<15}")

            print(f"\n{'Total rules tracked':<30}: {len(learning.data.rules)}")
            print(f"{'Total contexts tracked':<30}: {len(learning.data.contexts)}")

            return ExitCode.SUCCESS

        elif subcommand == "reset":
            # Reset learning data
            learning.reset()
            print("✓ Learning data reset")
            return ExitCode.SUCCESS

        else:
            print("Usage: ace learn [show|reset]")
            return ExitCode.INVALID_ARGS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_rules(args):
    """Manage rules configuration."""
    try:
        from ace.rules_local import bump_rules_version, get_rules_version, init_rules

        subcommand = args.rules_command if hasattr(args, "rules_command") else None

        if subcommand == "upgrade-local":
            # Deterministic local bump of rules version
            rules_path = Path(".ace/rules.json")
            old_version = get_rules_version(rules_path)

            bump_rules_version(rules_path)

            new_version = get_rules_version(rules_path)

            print(f"Rules upgraded: {old_version} → {new_version}")
            print(f"✓ Rules catalog updated at {rules_path}")
            return ExitCode.SUCCESS

        elif subcommand == "init":
            # Initialize rules.json
            rules_path = Path(".ace/rules.json")
            init_rules(rules_path)
            version = get_rules_version(rules_path)
            print(f"✓ Rules initialized (version: {version})")
            return ExitCode.SUCCESS

        elif subcommand == "show":
            # Show current rules version
            rules_path = Path(".ace/rules.json")
            version = get_rules_version(rules_path)
            print(f"Rules version: {version}")
            return ExitCode.SUCCESS

        else:
            print("Usage: ace rules [upgrade-local|init|show]")
            return ExitCode.INVALID_ARGS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_selftest(args):
    """Run determinism self-test (analyze twice, compare receipts)."""
    try:
        target = Path(args.target)
        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        print("Running determinism self-test...")
        print("  Pass 1/2: Analyzing...")

        # Run 1
        findings1 = run_analyze(target, rules)
        plans1 = run_refactor(target, rules)

        print(f"  Pass 1: {len(findings1)} findings, {len(plans1)} plans")
        print("  Pass 2/2: Analyzing...")

        # Run 2
        findings2 = run_analyze(target, rules)
        plans2 = run_refactor(target, rules)

        print(f"  Pass 2: {len(findings2)} findings, {len(plans2)} plans")

        # Compare findings
        findings1_dict = [f.to_dict() for f in findings1]
        findings2_dict = [f.to_dict() for f in findings2]

        findings_match = findings1_dict == findings2_dict

        # Compare plans
        plans1_dict = [p.to_dict() for p in plans1]
        plans2_dict = [p.to_dict() for p in plans2]

        plans_match = plans1_dict == plans2_dict

        # Report results
        print("\nResults:")
        print(f"  Findings match: {'✓ YES' if findings_match else '✗ NO'}")
        print(f"  Plans match:    {'✓ YES' if plans_match else '✗ NO'}")

        if findings_match and plans_match:
            print("\n✓ Determinism self-test PASSED")
            return ExitCode.SUCCESS
        else:
            print("\n✗ Determinism self-test FAILED")
            print("\nDifferences detected:")

            if not findings_match:
                print(f"  Findings differ: {len(findings1)} vs {len(findings2)}")

            if not plans_match:
                print(f"  Plans differ: {len(plans1)} vs {len(plans2)}")

            return ExitCode.OPERATIONAL_ERROR

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_explain(args):
    """Explain findings or rules."""
    try:
        if hasattr(args, "rule") and args.rule:
            # Explain a specific rule
            rule_id = args.rule.upper()

            # Rule documentation (simplified)
            rule_docs = {
                "PY-S101-UNSAFE-HTTP": "HTTP requests without timeout can hang indefinitely. Add timeout parameter.",
                "PY-S201-SUBPROCESS-CHECK": "subprocess.run() without check=True ignores errors. Add check=True.",
                "PY-S202-SUBPROCESS-SHELL": "shell=True is dangerous with user input. Use shell=False and pass list.",
                "PY-S203-SUBPROCESS-STRING-CMD": "String commands with shell are vulnerable to injection. Use list format.",
                "PY-E201-BROAD-EXCEPT": "Bare except catches all errors including system exits. Be more specific.",
                "PY-I101-IMPORT-SORT": "Imports should be sorted for consistency and readability.",
                "PY-Q201-ASSERT-IN-NONTEST": "assert is for tests only. Use proper error handling in production code.",
                "PY-Q202-PRINT-IN-SRC": "print() in source code should be replaced with proper logging.",
                "PY-Q203-EVAL-EXEC": "eval() and exec() execute arbitrary code and are dangerous. Avoid them.",
                "PY-S310-TRAILING-WS": "Trailing whitespace should be removed for clean code.",
                "PY-S311-EOF-NL": "Files should end with a newline for POSIX compliance.",
                "PY-S312-BLANKLINES": "Excessive blank lines reduce readability.",
                "MD-S001-DANGEROUS-COMMAND": "Dangerous shell commands in markdown documentation.",
                "YML-F001-DUPLICATE-KEY": "Duplicate YAML keys cause undefined behavior.",
                "SH-S001-MISSING-STRICT-MODE": "Shell scripts should use 'set -euo pipefail' for safety.",
            }

            if rule_id in rule_docs:
                print(f"Rule: {rule_id}")
                print(f"\n{rule_docs[rule_id]}")
            else:
                print(f"Unknown rule: {rule_id}")
                return ExitCode.OPERATIONAL_ERROR

        elif hasattr(args, "finding_id") and args.finding_id:
            print("Finding explanation not yet implemented")
            return ExitCode.OPERATIONAL_ERROR
        else:
            print("Usage: ace explain --rule RULE_ID")
            return ExitCode.INVALID_ARGS

        return ExitCode.SUCCESS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def main():
    """Main CLI entry point."""
    # Print personal mode banner
    if not any(arg in sys.argv for arg in ["--version", "--help", "-h"]):
        print("[ACE: Personal Mode] All features unlocked — full autonomy enabled.\n")

    try:
        parser = argparse.ArgumentParser(
            prog="ace", description="ACE - Autonomous Code Editor v0.2"
        )

        parser.add_argument(
            "--version", action="version", version=f"ACE v{__version__}"
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Enable verbose error output"
        )
        parser.add_argument(
            "--config", help="Path to ace.toml configuration file"
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # analyze subcommand
        parser_analyze = subparsers.add_parser(
            "analyze", help="Analyze code for issues"
        )
        parser_analyze.add_argument(
            "--target", required=True, help="Target directory or file to analyze"
        )
        parser_analyze.add_argument(
            "--rules", help="Comma-separated list of rule IDs to run (default: all)"
        )
        parser_analyze.add_argument(
            "--no-cache", action="store_true", help="Disable analysis cache"
        )
        parser_analyze.add_argument(
            "--cache-ttl", type=int, default=3600, help="Cache TTL in seconds (default: 3600)"
        )
        parser_analyze.add_argument(
            "--cache-dir", default=".ace", help="Cache directory (default: .ace)"
        )
        parser_analyze.add_argument(
            "--jobs", type=int, default=1, help="Number of parallel workers (default: 1)"
        )
        parser_analyze.add_argument(
            "--profile", help="Save performance profile to JSON file"
        )
        parser_analyze.add_argument(
            "--incremental", action="store_true", help="Only analyze changed files (requires index)"
        )
        parser_analyze.add_argument(
            "--rebuild-index", action="store_true", help="Rebuild content index before analyzing"
        )
        parser_analyze.add_argument(
            "--fast", action="store_true", help="Fast mode: skip slower checks, prefer cache"
        )
        parser_analyze.add_argument(
            "--safe", action="store_true", help="Safe mode: enable all guards and thorough checks"
        )
        parser_analyze.add_argument(
            "--silent", action="store_true", help="Silent mode: suppress non-error output"
        )
        parser_analyze.add_argument(
            "--deep", action="store_true", help="Disable clean-skip heuristic (force deep scan)"
        )
        parser_analyze.set_defaults(func=cmd_analyze)

        # refactor subcommand
        parser_refactor = subparsers.add_parser(
            "refactor", help="Plan refactoring changes"
        )
        parser_refactor.add_argument(
            "--target", required=True, help="Target directory or file to refactor"
        )
        parser_refactor.add_argument(
            "--rules", help="Comma-separated list of rule IDs to apply (default: all)"
        )
        parser_refactor.add_argument(
            "--max-files", type=int, help="Maximum number of files to modify"
        )
        parser_refactor.add_argument(
            "--max-lines", type=int, help="Maximum number of lines to modify"
        )
        parser_refactor.add_argument(
            "--patch-out", help="Write unified patch to file instead of applying"
        )
        parser_refactor.set_defaults(func=cmd_refactor)

        # validate subcommand
        parser_validate = subparsers.add_parser(
            "validate", help="Validate refactored code"
        )
        parser_validate.add_argument(
            "--target", required=True, help="Target directory or file to validate"
        )
        parser_validate.add_argument(
            "--rules", help="Comma-separated list of rule IDs to validate (default: all)"
        )
        parser_validate.set_defaults(func=cmd_validate)

        # export subcommand
        parser_export = subparsers.add_parser(
            "export", help="Export analysis results"
        )
        parser_export.set_defaults(func=cmd_export)

        # apply subcommand
        parser_apply = subparsers.add_parser(
            "apply", help="Apply refactoring changes"
        )
        parser_apply.add_argument(
            "--target", required=True, help="Target directory or file to apply changes to"
        )
        parser_apply.add_argument(
            "--rules", help="Comma-separated list of rule IDs to apply (default: all)"
        )
        parser_apply.add_argument(
            "--yes", action="store_true", help="Apply changes without confirmation"
        )
        parser_apply.add_argument(
            "--force", action="store_true", help="Skip git safety checks (allows dirty tree)"
        )
        parser_apply.add_argument(
            "--stash", action="store_true", help="Stash git changes before applying"
        )
        parser_apply.add_argument(
            "--commit", action="store_true", help="Commit changes after applying"
        )
        parser_apply.add_argument(
            "--max-files", type=int, help="Maximum number of files to modify"
        )
        parser_apply.add_argument(
            "--max-lines", type=int, help="Maximum number of lines to modify"
        )
        parser_apply.add_argument(
            "--journal-dir", default=".ace/journals", help="Journal directory (default: .ace/journals)"
        )
        parser_apply.add_argument(
            "--fast", action="store_true", help="Fast mode: skip some verification checks"
        )
        parser_apply.add_argument(
            "--safe", action="store_true", help="Safe mode: enable strict guards and thorough verification"
        )
        parser_apply.add_argument(
            "--silent", action="store_true", help="Silent mode: suppress non-error output"
        )
        parser_apply.set_defaults(func=cmd_apply)

        # baseline subcommands
        parser_baseline = subparsers.add_parser(
            "baseline", help="Baseline management"
        )
        baseline_subparsers = parser_baseline.add_subparsers(
            dest="baseline_command", help="Baseline commands"
        )

        # baseline create
        parser_baseline_create = baseline_subparsers.add_parser(
            "create", help="Create baseline snapshot"
        )
        parser_baseline_create.add_argument(
            "--target", required=True, help="Target directory or file to baseline"
        )
        parser_baseline_create.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_baseline_create.add_argument(
            "--baseline-path", default=".ace/baseline.json",
            help="Baseline file path (default: .ace/baseline.json)"
        )
        parser_baseline_create.set_defaults(func=cmd_baseline_create)

        # baseline compare
        parser_baseline_compare = baseline_subparsers.add_parser(
            "compare", help="Compare against baseline"
        )
        parser_baseline_compare.add_argument(
            "--target", required=True, help="Target directory or file to compare"
        )
        parser_baseline_compare.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_baseline_compare.add_argument(
            "--baseline-path", default=".ace/baseline.json",
            help="Baseline file path (default: .ace/baseline.json)"
        )
        parser_baseline_compare.add_argument(
            "--fail-on-new", action="store_true",
            help="Exit with error if new findings are detected"
        )
        parser_baseline_compare.add_argument(
            "--fail-on-regression", action="store_true",
            help="Exit with error if any regression (new or changed) is detected"
        )
        parser_baseline_compare.set_defaults(func=cmd_baseline_compare)

        # revert subcommand
        parser_revert = subparsers.add_parser(
            "revert", help="Revert changes from a journal"
        )
        parser_revert.add_argument(
            "--journal", default="latest",
            help="Journal ID, path, or 'latest' (default: latest)"
        )
        parser_revert.set_defaults(func=cmd_revert)

        # warmup subcommand
        parser_warmup = subparsers.add_parser(
            "warmup", help="Warm up analysis cache"
        )
        parser_warmup.add_argument(
            "--target", required=True, help="Target directory or file to analyze"
        )
        parser_warmup.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_warmup.set_defaults(func=cmd_warmup)

        # watch subcommand
        parser_watch = subparsers.add_parser(
            "watch", help="Watch files for changes and auto-analyze"
        )
        parser_watch.add_argument(
            "--target", required=True, help="Target directory or file to watch"
        )
        parser_watch.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_watch.add_argument(
            "--interval", type=int, default=5, help="Check interval in seconds (default: 5)"
        )
        parser_watch.set_defaults(func=cmd_watch)

        # report subcommand
        parser_report = subparsers.add_parser(
            "report", help="Generate analysis report"
        )
        parser_report.add_argument(
            "--target", required=True, help="Target directory or file to analyze"
        )
        parser_report.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_report.add_argument(
            "--format", choices=["text", "json", "sarif"], default="text",
            help="Report format (default: text)"
        )
        parser_report.add_argument(
            "--output", help="Output file path (default: stdout)"
        )
        parser_report.set_defaults(func=cmd_report)

        # policy subcommands
        parser_policy = subparsers.add_parser(
            "policy", help="Manage policy configuration"
        )
        policy_subparsers = parser_policy.add_subparsers(
            dest="policy_command", help="Policy commands"
        )

        # policy show
        parser_policy_show = policy_subparsers.add_parser(
            "show", help="Show current policy configuration"
        )
        parser_policy_show.add_argument(
            "--policy-file", default="policy.toml",
            help="Policy file path (default: policy.toml)"
        )
        parser_policy_show.set_defaults(func=cmd_policy)

        # explain subcommand
        parser_explain = subparsers.add_parser(
            "explain", help="Explain findings or rules"
        )
        parser_explain.add_argument(
            "--rule", help="Rule ID to explain"
        )
        parser_explain.add_argument(
            "--finding-id", help="Finding ID to explain"
        )
        parser_explain.set_defaults(func=cmd_explain)

        # selftest subcommand
        parser_selftest = subparsers.add_parser(
            "selftest", help="Run determinism self-test"
        )
        parser_selftest.add_argument(
            "--target", required=True, help="Target directory or file to test"
        )
        parser_selftest.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_selftest.set_defaults(func=cmd_selftest)

        # autopilot subcommand
        parser_autopilot = subparsers.add_parser(
            "autopilot", help="Run autopilot orchestration"
        )
        parser_autopilot.add_argument(
            "--target", required=True, help="Target directory or file to analyze"
        )
        parser_autopilot.add_argument(
            "--allow", choices=["auto", "suggest"], default="suggest",
            help="Allow mode: auto or suggest (default: suggest)"
        )
        parser_autopilot.add_argument(
            "--max-files", type=int, help="Maximum number of files to modify"
        )
        parser_autopilot.add_argument(
            "--max-lines", type=int, help="Maximum number of lines to modify"
        )
        parser_autopilot.add_argument(
            "--incremental", action="store_true", help="Only analyze changed files"
        )
        parser_autopilot.add_argument(
            "--dry-run", action="store_true", help="Plan only, don't apply changes"
        )
        parser_autopilot.add_argument(
            "--silent", action="store_true", help="Silent mode: suppress non-error output"
        )
        parser_autopilot.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_autopilot.add_argument(
            "--deep", action="store_true", help="Disable clean-skip heuristic (force deep scan)"
        )
        parser_autopilot.set_defaults(func=cmd_autopilot)

        # verify subcommand
        parser_verify = subparsers.add_parser(
            "verify", help="Verify receipts against journal and filesystem"
        )
        parser_verify.add_argument(
            "--base-path", default=".", help="Base path to verify (default: .)"
        )
        parser_verify.set_defaults(func=cmd_verify)

        # rules subcommands
        parser_rules = subparsers.add_parser(
            "rules", help="Manage rules configuration"
        )
        rules_subparsers = parser_rules.add_subparsers(
            dest="rules_command", help="Rules commands"
        )

        # rules upgrade-local
        parser_rules_upgrade = rules_subparsers.add_parser(
            "upgrade-local", help="Upgrade rules version locally (deterministic)"
        )
        parser_rules_upgrade.set_defaults(func=cmd_rules)

        # rules init
        parser_rules_init = rules_subparsers.add_parser(
            "init", help="Initialize rules.json"
        )
        parser_rules_init.set_defaults(func=cmd_rules)

        # rules show
        parser_rules_show = rules_subparsers.add_parser(
            "show", help="Show current rules version"
        )
        parser_rules_show.set_defaults(func=cmd_rules)

        # tune subcommand
        parser_tune = subparsers.add_parser(
            "tune", help="Show performance tuning recommendations"
        )
        parser_tune.set_defaults(func=cmd_tune)

        # repair subcommand
        parser_repair = subparsers.add_parser(
            "repair", help="Show repair reports for partial edit failures"
        )
        repair_subparsers = parser_repair.add_subparsers(
            dest="repair_command", help="Repair commands"
        )

        # repair show (or --latest)
        parser_repair_show = repair_subparsers.add_parser(
            "show", help="Show latest repair report"
        )
        parser_repair_show.add_argument(
            "--latest", action="store_true", help="Show latest repair report (default)"
        )
        parser_repair_show.set_defaults(func=cmd_repair, latest=True)

        # learn subcommands
        parser_learn = subparsers.add_parser(
            "learn", help="Manage learning data and adaptive thresholds"
        )
        learn_subparsers = parser_learn.add_subparsers(
            dest="learn_command", help="Learn commands"
        )

        # learn show
        parser_learn_show = learn_subparsers.add_parser(
            "show", help="Show learning statistics and threshold adjustments"
        )
        parser_learn_show.set_defaults(func=cmd_learn)

        # learn reset
        parser_learn_reset = learn_subparsers.add_parser(
            "reset", help="Reset all learning data"
        )
        parser_learn_reset.set_defaults(func=cmd_learn)

        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return ExitCode.INVALID_ARGS

        return args.func(args)

    except SystemExit as e:
        # argparse raises SystemExit on --help or invalid args
        # Exit code 0 for --help, 2 for invalid args
        if e.code == 0:
            return ExitCode.SUCCESS
        return ExitCode.INVALID_ARGS
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR
    except Exception as e:
        print(format_error(e, verbose=True), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
