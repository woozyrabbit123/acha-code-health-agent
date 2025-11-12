#!/usr/bin/env python3
"""
ACHA CLI - AI Code Health Agent
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from acha import __version__
from acha.agents.analysis_agent import AnalysisAgent
from acha.agents.refactor_agent import RefactorAgent
from acha.agents.validation_agent import ValidationAgent
from acha.baseline import compare_baseline, create_baseline
from acha.precommit import precommit_command
# Pro license removed - all features unlocked for personal use
from acha.utils.ast_cache import ASTCache
from acha.utils.checkpoint import checkpoint, restore
from acha.utils.exporter import build_proof_pack
from acha.utils.html_reporter import HTMLReporter
from acha.utils.logger import close_session_logger, init_session_logger, log_event
from acha.utils.policy import PolicyConfig, PolicyEnforcer
from acha.utils.sarif_reporter import SARIFReporter

# Force UTF-8 encoding on Windows to prevent charmap codec errors
if sys.platform == "win32":
    import io

    if sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def analyze(args):
    """Run code analysis"""
    # Support multiple targets for batch mode
    targets = getattr(args, "targets", None) or [args.target]

    # Setup cache if enabled
    cache = None
    use_cache = getattr(args, "cache", True)
    if use_cache:
        cache = ASTCache()

    # Setup parallel execution (fully unlocked)
    parallel = getattr(args, "parallel", False)
    jobs = getattr(args, "jobs", None)
    max_workers = getattr(args, "max_workers", 1)

    # Use --jobs if specified, otherwise use max_workers
    if jobs is not None:
        max_workers = jobs
        parallel = jobs > 1

    if len(targets) == 1:
        print(f"Analyzing code in: {targets[0]}")
    else:
        print(f"Analyzing code in {len(targets)} directories (batch mode)")

    # Run analysis
    agent = AnalysisAgent(cache=cache, parallel=parallel, max_workers=max_workers)
    try:
        if len(targets) > 1:
            result = agent.analyze_batch(targets)
        else:
            result = agent.run(targets[0])
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Get output format (all formats unlocked)
    output_format = getattr(args, "output_format", "json")

    # Always write JSON (required for other tools)
    json_path = reports_dir / "analysis.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)

    output_files = [str(json_path)]

    # Generate SARIF output if requested
    if output_format in ["sarif", "all"]:
        sarif_reporter = SARIFReporter(tool_name="ACHA", version="0.3.0")
        sarif_path = reports_dir / "analysis.sarif"
        sarif_reporter.generate_and_write(
            findings=result.get("findings", []),
            base_path=Path(targets[0]).resolve(),
            output_path=sarif_path,
        )
        output_files.append(str(sarif_path))

    # Generate HTML output if requested (Pro-gated above)
    if output_format in ["html", "all"]:
        html_reporter = HTMLReporter()
        html_path = reports_dir / "report.html"
        html_reporter.generate_and_write(
            output_path=html_path, analysis=result, target_path=targets[0]
        )
        output_files.append(str(html_path))

    # Print summary
    findings_count = len(result.get("findings", []))
    print("\nAnalysis complete!")
    print(f"Total findings: {findings_count}")
    print("Reports written to:")
    for output_file in output_files:
        print(f"  - {output_file}")

    # Count findings by type
    finding_types = {}
    for finding in result.get("findings", []):
        ftype = finding.get("finding", "unknown")
        finding_types[ftype] = finding_types.get(ftype, 0) + 1

    if finding_types:
        print("\nFindings by type:")
        for ftype, count in sorted(finding_types.items()):
            print(f"  {ftype}: {count}")

    return 0


def refactor(args):
    """Run code refactoring with safety rails"""
    import shutil
    import subprocess

    target_dir = args.target
    analysis_path = args.analysis
    fix_only = getattr(args, "fix", False)
    apply_changes = getattr(args, "apply", False)
    skip_confirmation = getattr(args, "yes", False)
    force = getattr(args, "force", False)

    # Default behavior: if neither --fix nor --apply is specified, use --fix (plan only)
    if not fix_only and not apply_changes:
        fix_only = True

    print(f"Refactoring code in: {target_dir}")
    print(f"Using analysis from: {analysis_path}")
    print(f"Mode: {'PLAN ONLY (--fix)' if fix_only else 'APPLY CHANGES (--apply)'}")

    # Parse refactor types
    refactor_types = None
    if hasattr(args, "refactor_types") and args.refactor_types:
        refactor_types = [rt.strip() for rt in args.refactor_types.split(",")]
        print(f"Refactor types: {', '.join(refactor_types)}")

    # Pre-flight checks for --apply
    if apply_changes:
        print("\n=== Pre-flight checks ===")

        # Dirty repo guard: abort if uncommitted changes (unless --force)
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                if not force:
                    print("❌ ERROR: Git working directory has uncommitted changes")
                    print("  Refusing to apply refactorings to dirty repository")
                    print("  Options:")
                    print("    1. Commit or stash your changes first")
                    print("    2. Use --force to override this check (not recommended)")
                    sys.exit(2)
                else:
                    print("⚠ Warning: Git working directory has uncommitted changes (--force override)")
            elif result.returncode == 0:
                print("✓ Git working directory is clean")
        except FileNotFoundError:
            if not force:
                print("❌ ERROR: git not found, cannot verify clean tree")
                print("  Use --force to override (not recommended)")
                sys.exit(2)
            else:
                print("⚠ Warning: git not found, skipping clean tree check (--force override)")

        # Create backup in acha_backup/ directory
        backup_root = Path("acha_backup")
        backup_root.mkdir(exist_ok=True)
        backup_dir = backup_root / f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        print(f"\nCreating backup: {backup_dir}")
        try:
            shutil.copytree(target_dir, backup_dir, symlinks=True)
            print(f"✓ Backup created at {backup_dir}")
        except Exception as e:
            print(f"✗ Failed to create backup: {e}")
            return 1

    # Run refactoring (always generates plan)
    agent = RefactorAgent(refactor_types=refactor_types)
    try:
        # Generate plan (diff)
        patch_summary = agent.apply(target_dir, analysis_path, plan_only=True)
    except Exception as e:
        print(f"Error during refactoring: {e}")
        return 1

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Write patch summary
    summary_path = reports_dir / "patch_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(patch_summary, f, indent=2, sort_keys=True)

    # Print summary
    print("\n=== Refactoring Plan ===")
    print(f"Patch ID: {patch_summary['patch_id']}")
    print(f"Files touched: {len(patch_summary['files_touched'])}")
    print(f"Lines added: {patch_summary['lines_added']}")
    print(f"Lines removed: {patch_summary['lines_removed']}")
    print("Diff written to: reports/patch.diff")
    print(f"Summary written to: {summary_path}")

    if patch_summary.get("notes"):
        print("\nNotes:")
        for note in patch_summary["notes"]:
            print(f"  - {note}")

    # If --fix only, stop here
    if fix_only:
        print("\n✓ Plan generated (use --apply to execute changes)")
        return 0

    # Apply changes if --apply specified
    if apply_changes:
        print("\n=== Applying Changes ===")

        # Confirmation prompt (unless --yes)
        if not skip_confirmation:
            response = input("\nApply these changes? [y/N]: ")
            if response.lower() not in ["y", "yes"]:
                print("❌ Aborted by user")
                return 1

        print("Applying modifications...")
        try:
            # Actually apply the changes
            from acha.utils.patcher import Patcher

            patcher = Patcher()
            patcher.prepare_workdir(target_dir)
            patcher.apply_modifications(agent.modifications)

            # Copy workdir back to target
            for file_path, new_content in agent.modifications.items():
                target_file = Path(target_dir) / file_path
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(new_content)

            print("✓ Changes applied successfully")
            print(f"  Backup available at: {backup_dir}")
            return 0
        except Exception as e:
            print(f"✗ Error applying changes: {e}")
            print(f"  Restore from backup: {backup_dir}")
            return 1


def validate(args):
    """Run validation"""
    target_dir = args.target

    # Determine which directory to validate
    workdir_path = Path("workdir")
    if workdir_path.exists():
        validate_dir = str(workdir_path)
        print(f"Validating refactored code in: {validate_dir}")
    else:
        validate_dir = target_dir
        print(f"No workdir found, validating original code in: {validate_dir}")

    # Load patch_id from patch_summary.json if available
    patch_id = "no-patch"
    patch_summary_path = Path("reports/patch_summary.json")
    if patch_summary_path.exists():
        with open(patch_summary_path, encoding="utf-8") as f:
            patch_summary = json.load(f)
            patch_id = patch_summary.get("patch_id", "no-patch")

    # Create checkpoint before validation
    checkpoint_dir = ".checkpoints/LATEST"
    print(f"Creating checkpoint at: {checkpoint_dir}")
    try:
        checkpoint(validate_dir, checkpoint_dir)
    except Exception as e:
        print(f"Warning: Failed to create checkpoint: {e}")

    # Run validation
    agent = ValidationAgent()
    print(f"Running tests with patch_id: {patch_id}")

    try:
        result = agent.run(validate_dir, patch_id)
    except Exception as e:
        print(f"Error during validation: {e}")
        return 1

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Write results to reports/validate.json
    validate_path = reports_dir / "validate.json"
    with open(validate_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print("\nValidation complete!")
    print(f"Status: {result['status'].upper()}")
    print(f"Tests run: {result['tests_run']}")
    print(f"Duration: {result['duration_s']}s")
    print(f"Report written to: {validate_path}")
    print("Test output saved to: reports/test_output.txt")

    # Handle failure - restore from checkpoint
    if result["status"] == "fail":
        print(f"\nTests FAILED - {len(result['failing_tests'])} failing test(s)")
        for test in result["failing_tests"]:
            print(f"  - {test}")

        print(f"\nRestoring from checkpoint to: {validate_dir}")
        try:
            restore(checkpoint_dir, validate_dir)
            print("✓ Restored to pre-refactor state")
        except Exception as e:
            print(f"✗ Failed to restore: {e}")

        return 1
    elif result["status"] == "pass":
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Validation error")
        return 1


def export(args):
    """Export results to proof pack"""
    print("Building proof pack...")

    try:
        zip_path = build_proof_pack()
        print("\n✓ Proof pack created successfully!")
        print(zip_path)
        return 0
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return 1
    except Exception as e:
        print(f"✗ Error creating proof pack: {e}")
        return 1


def run_pipeline_command(args, policy=None):
    """Run full pipeline: analyze → refactor → validate → export"""
    target_dir = args.target
    no_refactor = args.no_refactor
    fail_on_risky = args.fail_on_risky
    timeout = args.timeout

    # Parse refactor types
    refactor_types = None
    if hasattr(args, "refactor_types") and args.refactor_types:
        refactor_types = [rt.strip() for rt in args.refactor_types.split(",")]
    elif hasattr(args, "aggressive") and args.aggressive:
        refactor_types = [
            "inline_const",
            "remove_unused_import",
            "organize_imports",
            "harden_subprocess",
        ]

    log_event("pipeline_start", {"target": str(target_dir)})

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Setup logging
    log_path = reports_dir / "session.log"

    def log(msg: str):
        """Log message with ISO timestamp"""
        timestamp = datetime.utcnow().isoformat() + "Z"
        log_line = f"[{timestamp}] {msg}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
        print(msg)

    # Clear previous session log
    if log_path.exists():
        log_path.unlink()

    log("=" * 60)
    log("ACHA Full Pipeline Runner")
    log("=" * 60)
    log(f"Target directory: {target_dir}")
    log(f"No refactor: {no_refactor}")
    log(f"Fail on risky: {fail_on_risky}")
    log(f"Timeout: {timeout}s")
    if refactor_types:
        log(f"Refactor types: {', '.join(refactor_types)}")
    log("")

    # Step 1: ANALYZE
    log("STEP 1: ANALYZE")
    log("-" * 60)

    class Args:
        """Mock args object for internal function calls"""

        pass

    analyze_args = Args()
    analyze_args.target = target_dir
    # All output formats unlocked
    analyze_args.output_format = "all"
    analyze_args.parallel = True
    analyze_args.cache = True
    # Full parallel execution unlocked
    analyze_args.max_workers = 4
    analyze_args.jobs = None

    result = analyze(analyze_args)
    if result != 0:
        log("✗ Analysis failed")
        return 1

    # Load analysis results
    analysis_path = reports_dir / "analysis.json"
    with open(analysis_path, encoding="utf-8") as f:
        analysis_data = json.load(f)

    findings_count = len(analysis_data.get("findings", []))
    log(f"✓ Analysis complete: {findings_count} findings")
    log("")

    # Policy check if policy provided
    if policy:
        # Convert findings to issues format for policy enforcer
        issues_for_policy = []
        for finding in analysis_data.get("findings", []):
            issues_for_policy.append(
                {"rule": finding.get("finding", ""), "severity": finding.get("severity", "info")}
            )
        policy_results = {"issues": issues_for_policy}

        enforcer = PolicyEnforcer(policy)
        passed, reasons = enforcer.check_violations(policy_results)
        log_event("policy_check", {"passed": passed, "violations": reasons})
        if not passed:
            log("Policy violations detected: " + "; ".join(reasons))
            return 1

    # Check for risky constructs if --fail-on-risky
    if fail_on_risky:
        risky_findings = [
            f for f in analysis_data.get("findings", []) if f.get("finding") == "risky_construct"
        ]
        if risky_findings:
            log(
                f"✗ Found {len(risky_findings)} risky construct(s) - failing due to --fail-on-risky"
            )
            for finding in risky_findings:
                log(f"  {finding['file']}:{finding['start_line']} - {finding['rationale']}")
            return 1

    # Step 2: REFACTOR (skip if --no-refactor or no findings)
    patch_id = "no-patch"

    if no_refactor:
        log("STEP 2: REFACTOR (SKIPPED)")
        log("-" * 60)
        log("✓ Refactoring skipped due to --no-refactor flag")
        log("")

        # Create dummy patch_summary.json for export
        dummy_patch = {
            "patch_id": "no-patch",
            "files_touched": [],
            "lines_added": 0,
            "lines_removed": 0,
            "notes": ["Refactoring skipped via --no-refactor flag"],
        }
        with open(reports_dir / "patch_summary.json", "w", encoding="utf-8") as f:
            json.dump(dummy_patch, f, indent=2)
    elif findings_count == 0:
        log("STEP 2: REFACTOR (SKIPPED)")
        log("-" * 60)
        log("✓ No findings to refactor")
        log("")

        # Create dummy patch_summary.json for export
        dummy_patch = {
            "patch_id": "no-patch",
            "files_touched": [],
            "lines_added": 0,
            "lines_removed": 0,
            "notes": ["No findings to refactor"],
        }
        with open(reports_dir / "patch_summary.json", "w", encoding="utf-8") as f:
            json.dump(dummy_patch, f, indent=2)
    else:
        log("STEP 2: REFACTOR")
        log("-" * 60)

        refactor_args = Args()
        refactor_args.target = target_dir
        refactor_args.analysis = str(analysis_path)
        if refactor_types:
            refactor_args.refactor_types = ",".join(refactor_types)
        else:
            refactor_args.refactor_types = None

        result = refactor(refactor_args)
        if result != 0:
            log("✗ Refactoring failed")
            return 1

        # Load patch summary
        with open(reports_dir / "patch_summary.json", encoding="utf-8") as f:
            patch_data = json.load(f)
        patch_id = patch_data.get("patch_id", "no-patch")

        log(f"✓ Refactoring complete: patch_id={patch_id}")
        log("")

    # Step 3: VALIDATE
    log("STEP 3: VALIDATE")
    log("-" * 60)

    validate_args = Args()
    validate_args.target = target_dir
    validate_args.timeout = timeout

    result = validate(validate_args)

    # Load validation results
    validate_path = reports_dir / "validate.json"
    with open(validate_path, encoding="utf-8") as f:
        validate_data = json.load(f)

    status = validate_data.get("status", "unknown")

    if result != 0 or status != "pass":
        log(f"✗ Validation failed: status={status}")
        return 1

    log(
        f"✓ Validation passed: {validate_data.get('tests_run', 0)} tests in {validate_data.get('duration_s', 0)}s"
    )
    log("")

    # Step 4: EXPORT
    log("STEP 4: EXPORT")
    log("-" * 60)

    export_args = Args()

    result = export(export_args)
    if result != 0:
        log("✗ Export failed")
        return 1

    # Get ZIP path
    zip_path = Path("dist/release.zip").resolve()
    log(f"✓ Proof pack exported: {zip_path}")
    log("")

    # FINAL SUMMARY
    log("=" * 60)
    log("PIPELINE COMPLETE")
    log("=" * 60)
    log(f"Findings: {findings_count}")
    log(f"Patch ID: {patch_id}")
    log(f"Validation: {status}")
    log(f"Proof pack: {zip_path}")
    log(f"Session log: {log_path.resolve()}")
    log("=" * 60)

    return 0


def baseline_create_cmd(args):
    """Create baseline from analysis results"""
    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        print(f"Error: Analysis file not found: {args.analysis}", file=sys.stderr)
        return 1

    output_path = args.output or "baseline.json"

    # Load analysis
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    findings = analysis.get("findings", [])

    # Create baseline
    print(f"Creating baseline from {len(findings)} findings...")
    baseline = create_baseline(findings, output_path)

    print(f"✓ Baseline created: {output_path}")
    print(f"  Findings captured: {len(baseline['findings'])}")
    return 0


def baseline_compare_cmd(args):
    """Compare current findings against baseline"""
    analysis_path = Path(args.analysis)
    baseline_path = Path(args.baseline)

    if not analysis_path.exists():
        print(f"Error: Analysis file not found: {args.analysis}", file=sys.stderr)
        return 1

    if not baseline_path.exists():
        print(f"Error: Baseline file not found: {args.baseline}", file=sys.stderr)
        return 1

    # Load current analysis
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    current_findings = analysis.get("findings", [])

    # Compare
    print(f"Comparing {len(current_findings)} current findings against baseline...")
    comparison = compare_baseline(current_findings, str(baseline_path))

    # Print summary
    print("\nBaseline comparison results:")
    print(f"  New findings: {comparison['summary']['new_count']}")
    print(f"  Existing findings: {comparison['summary']['existing_count']}")
    print(f"  Fixed findings: {comparison['summary']['fixed_count']}")

    # Print new findings
    if comparison["new"]:
        print("\nNew findings:")
        for finding in comparison["new"]:
            file_path = finding.get("file", "unknown")
            line = finding.get("start_line", "?")
            rule = finding.get("rule", finding.get("finding", "unknown"))
            print(f"  {file_path}:{line} [{rule}]")

    # Print fixed findings
    if comparison["fixed"]:
        print(f"\nFixed findings ({len(comparison['fixed'])}):")
        for finding_id in list(comparison["fixed"])[:10]:  # Show first 10
            print(f"  {finding_id}")
        if len(comparison["fixed"]) > 10:
            print(f"  ... and {len(comparison['fixed']) - 10} more")

    # Write comparison to file
    output_path = Path("reports/baseline_comparison.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, sort_keys=True)

    print(f"\n✓ Comparison written to: {output_path}")

    # Exit 1 if new findings
    if comparison["new"]:
        return 1
    return 0


def precommit_cmd(args):
    """Run pre-commit scan"""
    target_dir = args.target
    baseline_path = args.baseline if hasattr(args, "baseline") else None

    return precommit_command(target_dir, baseline_path)


def main():
    parser = argparse.ArgumentParser(prog="acha", description="ACHA - AI Code Health Agent")

    # Global flags
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, help="Path to configuration file (JSON)")
    parser.add_argument("--policy", type=Path, help="Path to policy file (JSON quality gates)")
    parser.add_argument(
        "--format",
        choices=["text", "json", "jsonl"],
        default="text",
        help="Output format for stdout (default: text)",
    )
    parser.add_argument(
        "--session-log",
        type=Path,
        default=Path("reports/session.jsonl"),
        help="Path for JSONL session log",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze subcommand
    parser_analyze = subparsers.add_parser("analyze", help="Analyze code quality")
    parser_analyze.add_argument("--target", required=True, help="Target directory to analyze")
    parser_analyze.add_argument(
        "--output-format",
        choices=["json", "sarif", "html", "all"],
        default="json",
        help="Output format (default: json; html requires Pro)",
    )
    parser_analyze.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Enable parallel analysis (default: enabled; Pro required if > 1 worker)",
    )
    parser_analyze.add_argument(
        "--no-parallel", action="store_false", dest="parallel", help="Disable parallel analysis"
    )
    parser_analyze.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Number of worker threads (default: 1; Pro required if > 1)",
    )
    parser_analyze.add_argument(
        "--jobs",
        "-j",
        type=int,
        help="Number of parallel jobs (Pro required if > 1; overrides --max-workers)",
    )
    parser_analyze.add_argument(
        "--cache", action="store_true", default=True, help="Enable AST cache (default: enabled)"
    )
    parser_analyze.add_argument(
        "--no-cache", action="store_false", dest="cache", help="Disable AST cache"
    )
    parser_analyze.set_defaults(func=analyze)

    # refactor subcommand
    parser_refactor = subparsers.add_parser("refactor", help="Refactor code")
    parser_refactor.add_argument("--target", required=True, help="Target directory to refactor")
    parser_refactor.add_argument("--analysis", required=True, help="Path to analysis.json file")
    parser_refactor.add_argument(
        "--refactor-types",
        help="Comma-separated list of refactor types (default: inline_const,remove_unused_import)",
    )
    parser_refactor.add_argument(
        "--fix",
        action="store_true",
        help="Plan refactoring only (generate diff, no writes)",
    )
    parser_refactor.add_argument(
        "--apply",
        action="store_true",
        help="Apply refactoring changes (Pro required; writes to files)",
    )
    parser_refactor.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompts (use with --apply)",
    )
    parser_refactor.add_argument(
        "--force",
        action="store_true",
        help="Force apply changes even with dirty git tree (not recommended)",
    )
    parser_refactor.set_defaults(func=refactor)

    # validate subcommand
    parser_validate = subparsers.add_parser("validate", help="Validate changes")
    parser_validate.add_argument("--target", required=True, help="Target directory to validate")
    parser_validate.set_defaults(func=validate)

    # export subcommand
    parser_export = subparsers.add_parser("export", help="Export reports")
    parser_export.set_defaults(func=export)

    # run subcommand
    parser_run = subparsers.add_parser("run", help="Run full pipeline")
    parser_run.add_argument(
        "--target", default="./sample_project", help="Target directory (default: ./sample_project)"
    )
    parser_run.add_argument("--no-refactor", action="store_true", help="Skip refactoring step")
    parser_run.add_argument(
        "--fail-on-risky", action="store_true", help="Fail if risky constructs found"
    )
    parser_run.add_argument(
        "--timeout", type=int, default=30, help="Test timeout in seconds (default: 30)"
    )
    parser_run.add_argument("--refactor-types", help="Comma-separated list of refactor types")
    parser_run.add_argument("--aggressive", action="store_true", help="Enable all refactor types")
    parser_run.set_defaults(func=run_pipeline_command)

    # baseline subcommand (Pro-only)
    parser_baseline = subparsers.add_parser("baseline", help="Baseline management (Pro)")
    baseline_subs = parser_baseline.add_subparsers(
        dest="baseline_command", help="Baseline commands"
    )

    # baseline create
    parser_baseline_create = baseline_subs.add_parser(
        "create", help="Create baseline from analysis"
    )
    parser_baseline_create.add_argument(
        "--analysis", required=True, help="Path to analysis.json file"
    )
    parser_baseline_create.add_argument(
        "--output", "-o", help="Output path for baseline (default: baseline.json)"
    )
    parser_baseline_create.set_defaults(func=baseline_create_cmd)

    # baseline compare
    parser_baseline_compare = baseline_subs.add_parser(
        "compare", help="Compare analysis against baseline"
    )
    parser_baseline_compare.add_argument(
        "--analysis", required=True, help="Path to current analysis.json"
    )
    parser_baseline_compare.add_argument("--baseline", required=True, help="Path to baseline.json")
    parser_baseline_compare.set_defaults(func=baseline_compare_cmd)

    # precommit subcommand (Pro-only)
    parser_precommit = subparsers.add_parser("precommit", help="Pre-commit hook helper (Pro)")
    parser_precommit.add_argument(
        "--target", default=".", help="Target directory (default: current directory)"
    )
    parser_precommit.add_argument("--baseline", help="Optional baseline.json to compare against")
    parser_precommit.set_defaults(func=precommit_cmd)

    args = parser.parse_args()

    # Initialize session logger
    init_session_logger(args.session_log)
    log_event("cli_start", {"argv": sys.argv})

    try:
        # Load policy if provided
        policy_cfg = PolicyConfig.from_file(args.policy) if getattr(args, "policy", None) else None
        if policy_cfg:
            log_event("policy_loaded", policy_cfg.to_dict())

        if not args.command:
            parser.print_help()
            return 1

        # Dispatch to appropriate command
        if args.command == "run":
            result = run_pipeline_command(args, policy_cfg)
            # result is 0 on success, False or 1 on failure
            if result == 0:
                return 0
            else:
                return 1
        else:
            return args.func(args)
    finally:
        close_session_logger()


if __name__ == "__main__":
    sys.exit(main())
