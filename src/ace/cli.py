#!/usr/bin/env python3
"""ACE CLI - Autonomous Code Editor command-line interface."""

import argparse
import json
import sys
from pathlib import Path

from ace import __version__
from ace.kernel import run_analyze, run_apply, run_refactor, run_validate


def cmd_analyze(args):
    """Analyze code for issues across multiple languages."""
    target = Path(args.target)
    rules = args.rules.split(",") if args.rules else None

    findings = run_analyze(target, rules)

    # Output as JSON
    output = [f.to_dict() for f in findings]
    print(json.dumps(output, indent=2, sort_keys=True))

    return 0


def cmd_refactor(args):
    """Plan refactoring changes."""
    target = Path(args.target)
    rules = args.rules.split(",") if args.rules else None

    plans = run_refactor(target, rules)

    # Output as JSON
    output = [p.to_dict() for p in plans]
    print(json.dumps(output, indent=2, sort_keys=True))

    return 0


def cmd_validate(args):
    """Validate refactored code."""
    target = Path(args.target)
    rules = args.rules.split(",") if args.rules else None

    receipts = run_validate(target, rules)

    # Output as JSON
    print(json.dumps(receipts, indent=2, sort_keys=True))

    return 0


def cmd_export(args):
    """Export analysis results and receipts."""
    print("ACE v0.1 stub: export")
    return 0


def cmd_apply(args):
    """Apply refactoring changes with safety checks."""
    target = Path(args.target)
    rules = args.rules.split(",") if args.rules else None

    result = run_apply(target, rules, dry_run=not args.yes)

    if result == 0:
        print("Refactoring applied successfully")
    else:
        print("Refactoring failed")

    return result


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
    parser_analyze.add_argument(
        "--target", required=True, help="Target directory or file to analyze"
    )
    parser_analyze.add_argument(
        "--rules", help="Comma-separated list of rule IDs to run (default: all)"
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
    parser_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
