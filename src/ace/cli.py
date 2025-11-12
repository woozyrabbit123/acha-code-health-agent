#!/usr/bin/env python3
"""ACE CLI - Autonomous Code Editor command-line interface."""

import argparse
import sys

from ace import __version__
from ace.export import to_json
from ace.kernel import run_analyze, run_apply, run_refactor, run_validate


def cmd_analyze(args):
    """Analyze code for issues across multiple languages."""
    target = args.target
    output_format = args.format

    # Run analysis
    findings = run_analyze(target)

    # Print findings in requested format
    if output_format == "json":
        print(to_json([f.__dict__ for f in findings]))

    return 0


def cmd_refactor(args):
    """Plan refactoring changes."""
    target = args.target
    rule = getattr(args, "rule", None)

    # Run analysis and refactoring
    findings = run_analyze(target)

    # Filter by rule if specified
    if rule:
        findings = [f for f in findings if f.rule == rule]

    plans = run_refactor(target, findings)

    # Print plans
    print(to_json([p.__dict__ for p in plans]))

    return 0


def cmd_validate(args):
    """Validate refactored code."""
    target = args.target

    # Run full validation pipeline
    findings = run_analyze(target)
    plans = run_refactor(target, findings)
    receipts = run_validate(target, plans)

    # Print receipts
    print(to_json([r.__dict__ for r in receipts]))

    return 0


def cmd_export(args):
    """Export analysis results and receipts."""
    print("ACE v0.1 stub: export")
    return 0


def cmd_apply(args):
    """Apply refactoring changes with safety checks."""
    target = args.target

    # Run apply pipeline
    findings = run_analyze(target)
    plans = run_refactor(target, findings)
    exit_code = run_apply(target, plans)

    if exit_code == 0:
        print("✓ Refactoring applied successfully")
    else:
        print("✗ Refactoring failed")

    return exit_code


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ace", description="ACE - Autonomous Code Editor v0.1"
    )

    parser.add_argument(
        "--version", action="version", version=f"ACE v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze subcommand
    parser_analyze = subparsers.add_parser(
        "analyze", help="Analyze code for issues"
    )
    parser_analyze.add_argument("--target", required=True, help="Target directory or file")
    parser_analyze.add_argument("--format", default="json", choices=["json"], help="Output format")
    parser_analyze.set_defaults(func=cmd_analyze)

    # refactor subcommand
    parser_refactor = subparsers.add_parser(
        "refactor", help="Plan refactoring changes"
    )
    parser_refactor.add_argument("--target", required=True, help="Target directory or file")
    parser_refactor.add_argument("--rule", help="Filter by specific rule (e.g., py-s101)")
    parser_refactor.set_defaults(func=cmd_refactor)

    # validate subcommand
    parser_validate = subparsers.add_parser(
        "validate", help="Validate refactored code"
    )
    parser_validate.add_argument("--target", required=True, help="Target directory or file")
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
    parser_apply.add_argument("--target", required=True, help="Target directory or file")
    parser_apply.add_argument("--yes", action="store_true", help="Skip confirmation")
    parser_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
