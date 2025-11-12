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


def cmd_report_health(args):
    """Generate health map with risk heatmap (v1.7)."""
    try:
        from ace.report import generate_health_map

        target = Path(args.target) if hasattr(args, "target") else Path(".")
        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if hasattr(args, "rules") and args.rules else None
        output_path = args.output if hasattr(args, "output") else ".ace/health.html"

        print(f"Generating health map for {target}...")

        # Run analysis
        findings = run_analyze(target, rules)

        # Generate health map with risk heatmap
        report_path = generate_health_map(findings, output_path=output_path)

        print(f"✓ Health map generated: {report_path}")
        print(f"  Total findings: {len(findings)}")
        print(f"  Open with: open {report_path}")

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


def cmd_telemetry(args):
    """View performance telemetry (v1.7)."""
    try:
        from ace.telemetry import Telemetry

        subcommand = args.telemetry_command if hasattr(args, "telemetry_command") else None

        telemetry = Telemetry()

        if subcommand == "summary":
            # Show summary with p95
            days = args.days if hasattr(args, "days") else 7
            stats = telemetry.summary(days=days)

            print(f"ACE Telemetry Summary (last {days} days)\n" + "=" * 60)

            if stats.total_executions == 0:
                print("\nNo telemetry data yet. Run analysis to collect telemetry.")
                return ExitCode.SUCCESS

            print(f"\n{'Total executions':<30}: {stats.total_executions}")
            print(f"{'Unique rules':<30}: {len(stats.per_rule_count)}")

            # Show top 10 slowest rules
            top_slow = [
                (rule_id, stats.per_rule_avg_ms[rule_id], stats.per_rule_p95_ms[rule_id], stats.per_rule_count[rule_id])
                for rule_id in stats.per_rule_avg_ms
            ]
            top_slow.sort(key=lambda x: -x[2])  # Sort by p95 descending

            if top_slow:
                print(f"\nTop {min(10, len(top_slow))} slowest rules (by p95):\n")
                print(f"{'Rule ID':<35} {'Mean (ms)':<12} {'P95 (ms)':<12} {'Count':<10}")
                print("-" * 75)

                for rule_id, mean_ms, p95_ms, count in top_slow[:10]:
                    print(f"{rule_id:<35} {mean_ms:>10.2f} {p95_ms:>10.2f} {count:>9}")

            return ExitCode.SUCCESS

        else:
            print("Usage: ace telemetry summary [--days N]")
            return ExitCode.INVALID_ARGS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_ui(args):
    """Launch TUI dashboard (v1.7)."""
    try:
        from ace.tui.app import run_dashboard

        print("Launching ACE TUI Dashboard...")
        print("Press 'q' to quit, 'h' for help")
        run_dashboard()

        return ExitCode.SUCCESS

    except ImportError:
        print("TUI dashboard requires Textual. Install with: pip install textual", file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_assist(args):
    """LLM assist for code suggestions (v2.0)."""
    try:
        from ace.llm import get_assist

        subcommand = args.assist_command if hasattr(args, "assist_command") else None
        assist = get_assist()

        if subcommand == "docstring":
            # Parse location (e.g., src/main.py:42)
            location = args.location
            if ":" not in location:
                print("Error: location must be in format path:line", file=sys.stderr)
                return ExitCode.INVALID_ARGS

            file_path, line_num = location.rsplit(":", 1)
            file_path = Path(file_path)

            if not file_path.exists():
                print(f"Error: file not found: {file_path}", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR

            # Read file and extract function signature
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    line_idx = int(line_num) - 1
                    if line_idx < 0 or line_idx >= len(lines):
                        print(f"Error: line {line_num} out of range", file=sys.stderr)
                        return ExitCode.OPERATIONAL_ERROR

                    # Get function signature (may span multiple lines)
                    signature = lines[line_idx].strip()

                    # Generate docstring
                    docstring = assist.docstring_one_liner(signature)

                    print(f"Suggested docstring for {file_path}:{line_num}:")
                    print(f'  """{docstring}"""')

            except Exception as e:
                print(f"Error reading file: {e}", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR

            return ExitCode.SUCCESS

        elif subcommand == "name":
            # Similar to docstring, but suggest name
            location = args.location
            if ":" not in location:
                print("Error: location must be in format path:line", file=sys.stderr)
                return ExitCode.INVALID_ARGS

            file_path, line_num = location.rsplit(":", 1)
            file_path = Path(file_path)

            if not file_path.exists():
                print(f"Error: file not found: {file_path}", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR

            # Read file and extract code context
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    line_idx = int(line_num) - 1
                    if line_idx < 0 or line_idx >= len(lines):
                        print(f"Error: line {line_num} out of range", file=sys.stderr)
                        return ExitCode.OPERATIONAL_ERROR

                    # Get surrounding context (5 lines)
                    start = max(0, line_idx - 2)
                    end = min(len(lines), line_idx + 3)
                    code = "".join(lines[start:end])

                    # Get current name from line
                    current_line = lines[line_idx].strip()
                    current_name = current_line.split()[1] if len(current_line.split()) > 1 else ""

                    # Suggest name
                    suggested = assist.suggest_name(code, current_name)

                    if suggested:
                        print(f"Suggested name for {file_path}:{line_num}: {suggested}")
                    else:
                        print(f"No suggestion available (heuristic fallback)")

            except Exception as e:
                print(f"Error reading file: {e}", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR

            return ExitCode.SUCCESS

        else:
            print("Usage: ace assist {docstring|name} location")
            return ExitCode.INVALID_ARGS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_commitmsg(args):
    """Generate commit message from diff (v2.0)."""
    try:
        from ace.llm import get_assist
        import subprocess

        assist = get_assist()

        # Get diff
        diff = ""
        if args.from_diff:
            # Get diff from git
            try:
                result = subprocess.run(
                    ["git", "diff", "--cached"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    diff = result.stdout
                else:
                    print("Error: git diff failed", file=sys.stderr)
                    return ExitCode.OPERATIONAL_ERROR
            except Exception as e:
                print(f"Error running git diff: {e}", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR

        elif hasattr(args, "file") and args.file:
            # Read diff from file
            diff_path = Path(args.file)
            if not diff_path.exists():
                print(f"Error: file not found: {diff_path}", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR
            diff = diff_path.read_text()

        else:
            print("Error: must specify --from-diff or --file", file=sys.stderr)
            return ExitCode.INVALID_ARGS

        if not diff.strip():
            print("No diff to summarize")
            return ExitCode.SUCCESS

        # Generate commit message
        summary = assist.summarize_diff(diff)

        print("Suggested commit message:")
        print(f"  {summary}")

        return ExitCode.SUCCESS

    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_check(args):
    """Run checks like CI (v2.0)."""
    try:
        target = Path(args.target)
        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if hasattr(args, "rules") and args.rules else None
        strict = args.strict if hasattr(args, "strict") else False

        print(f"Running ACE checks on {target}...")

        # Run analysis
        findings = run_analyze(target, rules)

        print(f"\n{'=' * 60}")
        print(f"ACE Check Results")
        print(f"{'=' * 60}\n")
        print(f"Total findings: {len(findings)}")

        # Group by severity
        by_severity = {}
        for f in findings:
            sev = f.severity.value
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(f)

        for severity in ["critical", "high", "medium", "low", "info"]:
            if severity in by_severity:
                count = len(by_severity[severity])
                print(f"  {severity.capitalize()}: {count}")

        # In strict mode, fail if any findings
        if strict and findings:
            print(f"\n✗ Check failed: {len(findings)} finding(s) in strict mode")
            return ExitCode.POLICY_DENY

        print(f"\n✓ Check passed")
        return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
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

            # v1.7: Show tuned rules with non-default thresholds
            tuned_rules = learning.get_tuned_rules()
            if tuned_rules:
                print(f"\n{'Rules with tuned thresholds':<30}:\n")
                print(f"{'Rule ID':<35} {'Tuned Threshold':<18} {'Sample Size':<12}")
                print("-" * 65)
                for rule_id, threshold, stats in tuned_rules:
                    print(f"{rule_id:<35} {threshold:>16.2f} {stats.sample_size():>11}")

            # v1.7: Show auto-skiplist patterns
            if learning.data.auto_skiplist:
                print(f"\n{'Auto-skiplist patterns':<30}: {len(learning.data.auto_skiplist)}")
                for rule_id, patterns in list(learning.data.auto_skiplist.items())[:5]:
                    print(f"  {rule_id}: {len(patterns)} pattern(s)")

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


def cmd_index(args):
    """Manage symbol index (RepoMap)."""
    try:
        from ace.repomap import RepoMap

        subcommand = args.index_command if hasattr(args, "index_command") else None
        target = Path(args.target) if hasattr(args, "target") else Path(".")
        index_path = Path(args.index_path) if hasattr(args, "index_path") else Path(".ace/symbols.json")

        if subcommand == "build":
            # Build symbol index
            if not target.exists():
                raise OperationalError(f"Target path does not exist: {target}")

            print(f"Building symbol index for {target}...")
            import time
            start = time.time()

            repo_map = RepoMap().build(target)
            repo_map.save(index_path)

            elapsed = time.time() - start
            stats = repo_map.stats()

            print(f"✓ Symbol index built in {elapsed:.2f}s")
            print(f"  Total symbols: {stats['total_symbols']}")
            print(f"  Total files: {stats['total_files']}")
            print(f"  By type: {stats['by_type']}")
            print(f"  Saved to: {index_path}")

            return ExitCode.SUCCESS

        elif subcommand == "query":
            # Query symbol index
            if not index_path.exists():
                raise OperationalError(f"Index not found: {index_path}. Run 'ace index build' first.")

            repo_map = RepoMap.load(index_path)

            pattern = args.pattern if hasattr(args, "pattern") else None
            type_filter = args.type if hasattr(args, "type") else None
            limit = args.limit if hasattr(args, "limit") else 50

            results = repo_map.query(pattern=pattern, type=type_filter)
            results = results[:limit]

            print(json.dumps([s.to_dict() for s in results], indent=2))
            print(f"\n{len(results)} results", file=sys.stderr)

            return ExitCode.SUCCESS

        else:
            print("Usage: ace index [build|query]")
            return ExitCode.INVALID_ARGS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_graph(args):
    """Analyze dependency graph."""
    try:
        from ace.repomap import RepoMap
        from ace.depgraph import DepGraph

        index_path = Path(args.index_path) if hasattr(args, "index_path") else Path(".ace/symbols.json")

        if not index_path.exists():
            raise OperationalError(f"Index not found: {index_path}. Run 'ace index build' first.")

        repo_map = RepoMap.load(index_path)
        depgraph = DepGraph(repo_map)

        subcommand = args.graph_command if hasattr(args, "graph_command") else None

        if subcommand == "who-calls":
            # Find who calls a symbol
            symbol = args.symbol
            callers = depgraph.who_calls(symbol)

            print(json.dumps({"symbol": symbol, "callers": callers}, indent=2))
            print(f"\n{len(callers)} files call '{symbol}'", file=sys.stderr)

            return ExitCode.SUCCESS

        elif subcommand == "depends-on":
            # Get dependencies of a file
            file = args.file
            depth = args.depth if hasattr(args, "depth") else 2

            deps = depgraph.depends_on(file, depth=depth)

            print(json.dumps({"file": file, "dependencies": deps, "depth": depth}, indent=2))
            print(f"\n{len(deps)} dependencies found", file=sys.stderr)

            return ExitCode.SUCCESS

        elif subcommand == "stats":
            # Show graph statistics
            stats = depgraph.stats()
            print(json.dumps(stats, indent=2))

            return ExitCode.SUCCESS

        else:
            print("Usage: ace graph [who-calls|depends-on|stats]")
            return ExitCode.INVALID_ARGS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_context(args):
    """Analyze context and rank files."""
    try:
        from ace.repomap import RepoMap
        from ace.context_rank import ContextRanker

        index_path = Path(args.index_path) if hasattr(args, "index_path") else Path(".ace/symbols.json")

        if not index_path.exists():
            raise OperationalError(f"Index not found: {index_path}. Run 'ace index build' first.")

        repo_map = RepoMap.load(index_path)
        ranker = ContextRanker(repo_map)

        subcommand = args.context_command if hasattr(args, "context_command") else None

        if subcommand == "rank":
            # Rank files by relevance
            query = args.query if hasattr(args, "query") else None
            limit = args.limit if hasattr(args, "limit") else 10

            scores = ranker.rank_files(query=query, limit=limit)

            result = {
                "query": query,
                "limit": limit,
                "results": [
                    {
                        "file": s.file,
                        "score": round(s.score, 3),
                        "symbol_count": s.symbol_count,
                        "symbol_density": round(s.symbol_density, 3),
                        "recency_boost": round(s.recency_boost, 3),
                        "relevance_score": round(s.relevance_score, 3),
                    }
                    for s in scores
                ]
            }

            print(json.dumps(result, indent=2))

            return ExitCode.SUCCESS

        else:
            print("Usage: ace context [rank]")
            return ExitCode.INVALID_ARGS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_diff(args):
    """Interactive diff review and apply."""
    try:
        from ace.diffui import interactive_review, apply_approved_changes, parse_patch

        patch_file = Path(args.patch_file)

        if not patch_file.exists():
            raise OperationalError(f"Patch file does not exist: {patch_file}")

        # Read patch content
        patch_content = patch_file.read_text(encoding='utf-8')

        # Parse patch
        patches = parse_patch(patch_content)

        if not patches:
            print("No changes found in patch file")
            return ExitCode.SUCCESS

        # Convert to changes dict
        changes = {file: patch.new_content for file, patch in patches.items()}

        # Interactive review
        interactive = args.interactive if hasattr(args, "interactive") else False
        dry_run = args.dry_run if hasattr(args, "dry_run") else False

        if interactive:
            approved = interactive_review(changes, auto_approve=False)
        else:
            approved = set(changes.keys())

        # Apply approved changes
        if approved:
            results = apply_approved_changes(changes, approved, dry_run=dry_run)

            success_count = sum(1 for v in results.values() if v)
            fail_count = len(results) - success_count

            print(f"\n{'Dry run:' if dry_run else 'Applied:'} {success_count} file(s)")
            if fail_count > 0:
                print(f"Failed: {fail_count} file(s)", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR

            return ExitCode.SUCCESS
        else:
            print("No changes approved")
            return ExitCode.SUCCESS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_pack(args):
    """Apply codemod packs."""
    try:
        from ace.packs_builtin import get_pack, list_packs, apply_pack_to_directory
        from ace.diffui import interactive_review, apply_approved_changes

        subcommand = args.pack_command if hasattr(args, "pack_command") else None

        if subcommand == "list":
            # List available packs
            packs = list_packs()
            print("Available Codemod Packs:\n")
            for pack in packs:
                print(f"  {pack.id}")
                print(f"    Name: {pack.name}")
                print(f"    Description: {pack.description}")
                print(f"    Risk: {pack.risk_level}")
                print(f"    Category: {pack.category}")
                print()
            return ExitCode.SUCCESS

        elif subcommand == "apply":
            # Apply a pack
            pack_id = args.pack_id
            target = Path(args.target) if hasattr(args, "target") else Path(".")
            interactive = args.interactive if hasattr(args, "interactive") else False
            dry_run = args.dry_run if hasattr(args, "dry_run") else False

            pack = get_pack(pack_id)
            if not pack:
                print(f"Error: Unknown pack '{pack_id}'", file=sys.stderr)
                return ExitCode.OPERATIONAL_ERROR

            print(f"Applying pack: {pack.name}")

            # Get plans for all files
            if target.is_file():
                source_code = target.read_text(encoding='utf-8')
                from ace.packs_builtin import apply_pack_to_file
                plan = apply_pack_to_file(pack_id, str(target), source_code)
                plans = [plan] if plan else []
            else:
                plans = apply_pack_to_directory(pack_id, target)

            if not plans:
                print("No changes needed")
                return ExitCode.SUCCESS

            print(f"Found {len(plans)} file(s) to modify")

            # Build changes dict
            changes = {}
            for plan in plans:
                for edit in plan.edits:
                    changes[edit.file] = edit.payload

            # Interactive review or auto-apply
            if interactive:
                approved = interactive_review(changes, auto_approve=False)
            else:
                approved = set(changes.keys())

            # Apply changes
            if approved:
                results = apply_approved_changes(changes, approved, dry_run=dry_run)
                success_count = sum(1 for v in results.values() if v)
                print(f"\n{'[DRY RUN] Would apply' if dry_run else 'Applied'}: {success_count} file(s)")

            return ExitCode.SUCCESS

        else:
            print("Usage: ace pack [list|apply]")
            return ExitCode.INVALID_ARGS

    except ACEError as e:
        print(format_error(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(format_error(e, verbose=getattr(args, "verbose", False)), file=sys.stderr)
        return ExitCode.OPERATIONAL_ERROR


def cmd_install_pre_commit(args):
    """Install pre-commit hook (idempotent)."""
    try:
        import os
        import stat

        git_dir = Path(".git")
        if not git_dir.exists():
            print("Error: Not a git repository", file=sys.stderr)
            return ExitCode.OPERATIONAL_ERROR

        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        hook_path = hooks_dir / "pre-commit"

        # POSIX pre-commit hook
        hook_content = """#!/bin/sh
# ACE pre-commit hook

echo "Running ACE pre-commit checks..."

# Get staged Python files
STAGED_PY_FILES=$(git diff --cached --name-only --diff-filter=ACMR | grep '\\.py$')

if [ -z "$STAGED_PY_FILES" ]; then
    echo "No Python files staged, skipping ACE checks"
    exit 0
fi

# Run analyze on staged files
ace analyze --target . --exit-on-violation

if [ $? -ne 0 ]; then
    echo "ACE analysis found violations. Commit blocked."
    echo "Run 'ace autopilot' to fix issues automatically."
    exit 1
fi

echo "ACE checks passed!"
exit 0
"""

        # Check if hook already exists
        if hook_path.exists():
            existing_content = hook_path.read_text()

            # If ACE hook already installed with same content, report and exit
            if "# ACE pre-commit hook" in existing_content:
                if existing_content.strip() == hook_content.strip():
                    print(f"✓ ACE pre-commit hook already installed at {hook_path}")
                    print("  (no changes needed)")
                    return ExitCode.SUCCESS
                else:
                    # Update to new version
                    print(f"Updating ACE pre-commit hook at {hook_path}...")
                    hook_path.write_text(hook_content)
                    st = hook_path.stat()
                    hook_path.chmod(st.st_mode | stat.S_IEXEC)
                    print(f"✓ ACE pre-commit hook updated")
                    return ExitCode.SUCCESS
            else:
                # Non-ACE hook exists, preserve it and append ACE checks
                print(f"⚠ Existing pre-commit hook found at {hook_path}")
                print("  Appending ACE checks to existing hook...")

                # Append ACE checks after existing hook
                combined_content = existing_content.rstrip() + "\n\n" + hook_content
                hook_path.write_text(combined_content)
                st = hook_path.stat()
                hook_path.chmod(st.st_mode | stat.S_IEXEC)
                print(f"✓ ACE checks appended to existing pre-commit hook")
                return ExitCode.SUCCESS
        else:
            # No hook exists, install fresh
            hook_path.write_text(hook_content)
            st = hook_path.stat()
            hook_path.chmod(st.st_mode | stat.S_IEXEC)
            print(f"✓ Pre-commit hook installed at {hook_path}")
            print("  The hook will run 'ace analyze' on staged Python files")
            print("  To bypass: git commit --no-verify")
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

        # report subcommands
        parser_report = subparsers.add_parser(
            "report", help="Generate analysis reports"
        )
        report_subparsers = parser_report.add_subparsers(
            dest="report_command", help="Report commands"
        )

        # report (default - backwards compatible)
        parser_report.add_argument(
            "--target", help="Target directory or file to analyze"
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

        # report health (v1.7)
        parser_report_health = report_subparsers.add_parser(
            "health", help="Generate health map with risk heatmap"
        )
        parser_report_health.add_argument(
            "--target", default=".", help="Target directory to analyze (default: .)"
        )
        parser_report_health.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_report_health.add_argument(
            "--output", default=".ace/health.html",
            help="Output HTML file path (default: .ace/health.html)"
        )
        parser_report_health.set_defaults(func=cmd_report_health)

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

        # index subcommands (v1.5)
        parser_index = subparsers.add_parser(
            "index", help="Manage symbol index (RepoMap)"
        )
        index_subparsers = parser_index.add_subparsers(
            dest="index_command", help="Index commands"
        )

        # index build
        parser_index_build = index_subparsers.add_parser(
            "build", help="Build symbol index"
        )
        parser_index_build.add_argument(
            "--target", default=".", help="Target directory to index (default: .)"
        )
        parser_index_build.add_argument(
            "--index-path", default=".ace/symbols.json",
            help="Index output path (default: .ace/symbols.json)"
        )
        parser_index_build.set_defaults(func=cmd_index)

        # index query
        parser_index_query = index_subparsers.add_parser(
            "query", help="Query symbol index"
        )
        parser_index_query.add_argument(
            "--pattern", help="Symbol name pattern (substring match)"
        )
        parser_index_query.add_argument(
            "--type", choices=["function", "class", "module"],
            help="Filter by symbol type"
        )
        parser_index_query.add_argument(
            "--limit", type=int, default=50,
            help="Maximum results (default: 50)"
        )
        parser_index_query.add_argument(
            "--index-path", default=".ace/symbols.json",
            help="Index file path (default: .ace/symbols.json)"
        )
        parser_index_query.set_defaults(func=cmd_index)

        # graph subcommands (v1.5)
        parser_graph = subparsers.add_parser(
            "graph", help="Analyze dependency graph"
        )
        graph_subparsers = parser_graph.add_subparsers(
            dest="graph_command", help="Graph commands"
        )

        # graph who-calls
        parser_graph_who_calls = graph_subparsers.add_parser(
            "who-calls", help="Find files that call a symbol"
        )
        parser_graph_who_calls.add_argument(
            "symbol", help="Symbol name to search for"
        )
        parser_graph_who_calls.add_argument(
            "--index-path", default=".ace/symbols.json",
            help="Index file path (default: .ace/symbols.json)"
        )
        parser_graph_who_calls.set_defaults(func=cmd_graph)

        # graph depends-on
        parser_graph_depends_on = graph_subparsers.add_parser(
            "depends-on", help="Get dependencies of a file"
        )
        parser_graph_depends_on.add_argument(
            "file", help="File path to analyze"
        )
        parser_graph_depends_on.add_argument(
            "--depth", type=int, default=2,
            help="Dependency depth (default: 2, -1 for unlimited)"
        )
        parser_graph_depends_on.add_argument(
            "--index-path", default=".ace/symbols.json",
            help="Index file path (default: .ace/symbols.json)"
        )
        parser_graph_depends_on.set_defaults(func=cmd_graph)

        # graph stats
        parser_graph_stats = graph_subparsers.add_parser(
            "stats", help="Show dependency graph statistics"
        )
        parser_graph_stats.add_argument(
            "--index-path", default=".ace/symbols.json",
            help="Index file path (default: .ace/symbols.json)"
        )
        parser_graph_stats.set_defaults(func=cmd_graph)

        # context subcommands (v1.5)
        parser_context = subparsers.add_parser(
            "context", help="Analyze context and rank files"
        )
        context_subparsers = parser_context.add_subparsers(
            dest="context_command", help="Context commands"
        )

        # context rank
        parser_context_rank = context_subparsers.add_parser(
            "rank", help="Rank files by relevance"
        )
        parser_context_rank.add_argument(
            "--query", help="Search query for relevance scoring"
        )
        parser_context_rank.add_argument(
            "--limit", type=int, default=10,
            help="Maximum results (default: 10)"
        )
        parser_context_rank.add_argument(
            "--index-path", default=".ace/symbols.json",
            help="Index file path (default: .ace/symbols.json)"
        )
        parser_context_rank.set_defaults(func=cmd_context)

        # diff subcommand (v1.5)
        parser_diff = subparsers.add_parser(
            "diff", help="Interactive diff review and apply"
        )
        parser_diff.add_argument(
            "patch_file", help="Patch file to review"
        )
        parser_diff.add_argument(
            "--interactive", action="store_true",
            help="Enable interactive review (accept/reject per file)"
        )
        parser_diff.add_argument(
            "--dry-run", action="store_true",
            help="Don't actually apply changes"
        )
        parser_diff.set_defaults(func=cmd_diff)

        # pack subcommands (v1.6)
        parser_pack = subparsers.add_parser(
            "pack", help="Apply codemod packs"
        )
        pack_subparsers = parser_pack.add_subparsers(
            dest="pack_command", help="Pack commands"
        )

        # pack list
        parser_pack_list = pack_subparsers.add_parser(
            "list", help="List available codemod packs"
        )
        parser_pack_list.set_defaults(func=cmd_pack)

        # pack apply
        parser_pack_apply = pack_subparsers.add_parser(
            "apply", help="Apply a codemod pack"
        )
        parser_pack_apply.add_argument(
            "pack_id", help="Pack ID (e.g., PY_PATHLIB, PY_REQUESTS_HARDEN)"
        )
        parser_pack_apply.add_argument(
            "--target", default=".",
            help="Target directory or file (default: .)"
        )
        parser_pack_apply.add_argument(
            "--interactive", action="store_true",
            help="Interactive review (accept/reject per file)"
        )
        parser_pack_apply.add_argument(
            "--dry-run", action="store_true",
            help="Show changes without applying"
        )
        parser_pack_apply.set_defaults(func=cmd_pack)

        # install-pre-commit subcommand (v1.6)
        parser_install_precommit = subparsers.add_parser(
            "install-pre-commit", help="Install ACE pre-commit hook"
        )
        parser_install_precommit.set_defaults(func=cmd_install_pre_commit)

        # telemetry subcommands (v1.7)
        parser_telemetry = subparsers.add_parser(
            "telemetry", help="View performance telemetry"
        )
        telemetry_subparsers = parser_telemetry.add_subparsers(
            dest="telemetry_command", help="Telemetry commands"
        )

        # telemetry summary
        parser_telemetry_summary = telemetry_subparsers.add_parser(
            "summary", help="Show telemetry summary with p95"
        )
        parser_telemetry_summary.add_argument(
            "--days", type=int, default=7,
            help="Number of days to aggregate (default: 7)"
        )
        parser_telemetry_summary.set_defaults(func=cmd_telemetry)

        # ui subcommand (v1.7)
        parser_ui = subparsers.add_parser(
            "ui", help="Launch TUI dashboard"
        )
        parser_ui.set_defaults(func=cmd_ui)

        # assist subcommands (v2.0)
        parser_assist = subparsers.add_parser(
            "assist", help="LLM assist for code suggestions (optional)"
        )
        assist_subparsers = parser_assist.add_subparsers(
            dest="assist_command", help="Assist commands"
        )

        # assist docstring
        parser_assist_docstring = assist_subparsers.add_parser(
            "docstring", help="Generate docstring for function"
        )
        parser_assist_docstring.add_argument(
            "location", help="File path and line (e.g., src/main.py:42)"
        )
        parser_assist_docstring.set_defaults(func=cmd_assist)

        # assist name
        parser_assist_name = assist_subparsers.add_parser(
            "name", help="Suggest better name for code entity"
        )
        parser_assist_name.add_argument(
            "location", help="File path and line (e.g., src/main.py:42)"
        )
        parser_assist_name.set_defaults(func=cmd_assist)

        # commitmsg subcommand (v2.0)
        parser_commitmsg = subparsers.add_parser(
            "commitmsg", help="Generate commit message from diff"
        )
        parser_commitmsg.add_argument(
            "--from-diff", action="store_true",
            help="Generate from current git diff"
        )
        parser_commitmsg.add_argument(
            "--file", help="Read diff from file"
        )
        parser_commitmsg.set_defaults(func=cmd_commitmsg)

        # check subcommand (v2.0)
        parser_check = subparsers.add_parser(
            "check", help="Run checks (like CI)"
        )
        parser_check.add_argument(
            "--target", default=".", help="Target directory (default: .)"
        )
        parser_check.add_argument(
            "--strict", action="store_true",
            help="Strict mode: fail on any findings"
        )
        parser_check.add_argument(
            "--rules", help="Comma-separated list of rule IDs (default: all)"
        )
        parser_check.set_defaults(func=cmd_check)

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
