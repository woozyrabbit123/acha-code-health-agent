#!/usr/bin/env python3
"""
ACHA CLI - AI Code Health Agent
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from agents.analysis_agent import AnalysisAgent
from agents.refactor_agent import RefactorAgent
from agents.validation_agent import ValidationAgent
from utils.checkpoint import checkpoint, restore
from utils.exporter import build_proof_pack
from utils.logger import init_session_logger, log_event, close_session_logger
from utils.policy import PolicyConfig, PolicyEnforcer


def analyze(args):
    """Run code analysis"""
    target_dir = args.target

    print(f"Analyzing code in: {target_dir}")

    # Run analysis
    agent = AnalysisAgent()
    try:
        result = agent.run(target_dir)
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Write results to reports/analysis.json
    output_path = reports_dir / "analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    # Print summary
    findings_count = len(result.get('findings', []))
    print(f"\nAnalysis complete!")
    print(f"Total findings: {findings_count}")
    print(f"Report written to: {output_path}")

    # Count findings by type
    finding_types = {}
    for finding in result.get('findings', []):
        ftype = finding.get('finding', 'unknown')
        finding_types[ftype] = finding_types.get(ftype, 0) + 1

    if finding_types:
        print("\nFindings by type:")
        for ftype, count in sorted(finding_types.items()):
            print(f"  {ftype}: {count}")

    return 0


def refactor(args):
    """Run code refactoring"""
    target_dir = args.target
    analysis_path = args.analysis

    print(f"Refactoring code in: {target_dir}")
    print(f"Using analysis from: {analysis_path}")

    # Parse refactor types
    refactor_types = None
    if hasattr(args, 'refactor_types') and args.refactor_types:
        refactor_types = [rt.strip() for rt in args.refactor_types.split(',')]
        print(f"Refactor types: {', '.join(refactor_types)}")

    # Run refactoring
    agent = RefactorAgent(refactor_types=refactor_types)
    try:
        patch_summary = agent.apply(target_dir, analysis_path)
    except Exception as e:
        print(f"Error during refactoring: {e}")
        return 1

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Write patch summary to reports/patch_summary.json
    summary_path = reports_dir / "patch_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(patch_summary, f, indent=2)

    # Print summary
    print(f"\nRefactoring complete!")
    print(f"Patch ID: {patch_summary['patch_id']}")
    print(f"Files touched: {len(patch_summary['files_touched'])}")
    print(f"Lines added: {patch_summary['lines_added']}")
    print(f"Lines removed: {patch_summary['lines_removed']}")
    print(f"Diff written to: dist/patch.diff")
    print(f"Summary written to: {summary_path}")

    if patch_summary.get('notes'):
        print("\nNotes:")
        for note in patch_summary['notes']:
            print(f"  - {note}")

    return 0


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
        with open(patch_summary_path, 'r', encoding='utf-8') as f:
            patch_summary = json.load(f)
            patch_id = patch_summary.get('patch_id', 'no-patch')

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
    with open(validate_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"\nValidation complete!")
    print(f"Status: {result['status'].upper()}")
    print(f"Tests run: {result['tests_run']}")
    print(f"Duration: {result['duration_s']}s")
    print(f"Report written to: {validate_path}")
    print(f"Test output saved to: reports/test_output.txt")

    # Handle failure - restore from checkpoint
    if result['status'] == 'fail':
        print(f"\nTests FAILED - {len(result['failing_tests'])} failing test(s)")
        for test in result['failing_tests']:
            print(f"  - {test}")

        print(f"\nRestoring from checkpoint to: {validate_dir}")
        try:
            restore(checkpoint_dir, validate_dir)
            print("✓ Restored to pre-refactor state")
        except Exception as e:
            print(f"✗ Failed to restore: {e}")

        return 1
    elif result['status'] == 'pass':
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ Validation error")
        return 1


def export(args):
    """Export results to proof pack"""
    print("Building proof pack...")

    try:
        zip_path = build_proof_pack()
        print(f"\n✓ Proof pack created successfully!")
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
    if hasattr(args, 'refactor_types') and args.refactor_types:
        refactor_types = [rt.strip() for rt in args.refactor_types.split(',')]
    elif hasattr(args, 'aggressive') and args.aggressive:
        refactor_types = ["inline_const", "remove_unused_import", "organize_imports", "harden_subprocess"]

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
        with open(log_path, 'a', encoding='utf-8') as f:
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

    result = analyze(analyze_args)
    if result != 0:
        log("✗ Analysis failed")
        return 1

    # Load analysis results
    analysis_path = reports_dir / "analysis.json"
    with open(analysis_path, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)

    findings_count = len(analysis_data.get('findings', []))
    log(f"✓ Analysis complete: {findings_count} findings")
    log("")

    # Policy check if policy provided
    if policy:
        # Convert findings to issues format for policy enforcer
        issues_for_policy = []
        for finding in analysis_data.get('findings', []):
            issues_for_policy.append({
                "rule": finding.get("finding", ""),
                "severity": finding.get("severity", "info")
            })
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
            f for f in analysis_data.get('findings', [])
            if f.get('finding') == 'risky_construct'
        ]
        if risky_findings:
            log(f"✗ Found {len(risky_findings)} risky construct(s) - failing due to --fail-on-risky")
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
            "notes": ["Refactoring skipped via --no-refactor flag"]
        }
        with open(reports_dir / "patch_summary.json", 'w', encoding='utf-8') as f:
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
            "notes": ["No findings to refactor"]
        }
        with open(reports_dir / "patch_summary.json", 'w', encoding='utf-8') as f:
            json.dump(dummy_patch, f, indent=2)
    else:
        log("STEP 2: REFACTOR")
        log("-" * 60)

        refactor_args = Args()
        refactor_args.target = target_dir
        refactor_args.analysis = str(analysis_path)
        if refactor_types:
            refactor_args.refactor_types = ','.join(refactor_types)
        else:
            refactor_args.refactor_types = None

        result = refactor(refactor_args)
        if result != 0:
            log("✗ Refactoring failed")
            return 1

        # Load patch summary
        with open(reports_dir / "patch_summary.json", 'r', encoding='utf-8') as f:
            patch_data = json.load(f)
        patch_id = patch_data.get('patch_id', 'no-patch')

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
    with open(validate_path, 'r', encoding='utf-8') as f:
        validate_data = json.load(f)

    status = validate_data.get('status', 'unknown')

    if result != 0 or status != 'pass':
        log(f"✗ Validation failed: status={status}")
        return 1

    log(f"✓ Validation passed: {validate_data.get('tests_run', 0)} tests in {validate_data.get('duration_s', 0)}s")
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


def main():
    parser = argparse.ArgumentParser(
        prog='acha',
        description='ACHA - AI Code Health Agent'
    )

    # Global flags
    parser.add_argument("--config", type=Path, help="Path to configuration file (JSON)")
    parser.add_argument("--policy", type=Path, help="Path to policy file (JSON quality gates)")
    parser.add_argument("--format", choices=["text", "json", "jsonl"], default="text",
                        help="Output format for stdout (default: text)")
    parser.add_argument("--session-log", type=Path, default=Path("reports/session.jsonl"),
                        help="Path for JSONL session log")

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # analyze subcommand
    parser_analyze = subparsers.add_parser('analyze', help='Analyze code quality')
    parser_analyze.add_argument('--target', required=True, help='Target directory to analyze')
    parser_analyze.set_defaults(func=analyze)

    # refactor subcommand
    parser_refactor = subparsers.add_parser('refactor', help='Refactor code')
    parser_refactor.add_argument('--target', required=True, help='Target directory to refactor')
    parser_refactor.add_argument('--analysis', required=True, help='Path to analysis.json file')
    parser_refactor.add_argument('--refactor-types', help='Comma-separated list of refactor types (default: inline_const,remove_unused_import)')
    parser_refactor.set_defaults(func=refactor)

    # validate subcommand
    parser_validate = subparsers.add_parser('validate', help='Validate changes')
    parser_validate.add_argument('--target', required=True, help='Target directory to validate')
    parser_validate.set_defaults(func=validate)

    # export subcommand
    parser_export = subparsers.add_parser('export', help='Export reports')
    parser_export.set_defaults(func=export)

    # run subcommand
    parser_run = subparsers.add_parser('run', help='Run full pipeline')
    parser_run.add_argument('--target', default='./sample_project', help='Target directory (default: ./sample_project)')
    parser_run.add_argument('--no-refactor', action='store_true', help='Skip refactoring step')
    parser_run.add_argument('--fail-on-risky', action='store_true', help='Fail if risky constructs found')
    parser_run.add_argument('--timeout', type=int, default=30, help='Test timeout in seconds (default: 30)')
    parser_run.add_argument('--refactor-types', help='Comma-separated list of refactor types')
    parser_run.add_argument('--aggressive', action='store_true', help='Enable all refactor types')
    parser_run.set_defaults(func=run_pipeline_command)

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


if __name__ == '__main__':
    sys.exit(main())
