#!/usr/bin/env python3
"""ACE CLI - Autonomous Code Editor command-line interface."""

import argparse
import json
import sys
from pathlib import Path

from ace import __version__
from ace.errors import (
    ACEError,
    ExitCode,
    InvalidArgsError,
    OperationalError,
    PolicyDenyError,
    format_error,
)
from ace.kernel import run_analyze, run_apply, run_refactor, run_validate


def cmd_analyze(args):
    """Analyze code for issues across multiple languages."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        findings = run_analyze(target, rules)

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


def cmd_apply(args):
    """Apply refactoring changes with safety checks."""
    try:
        target = Path(args.target)

        if not target.exists():
            raise OperationalError(f"Target path does not exist: {target}")

        rules = args.rules.split(",") if args.rules else None

        exit_code, receipts = run_apply(
            target,
            rules,
            dry_run=not args.yes,
            force=args.force,
            stash=args.stash,
            commit=args.commit,
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


def main():
    """Main CLI entry point."""
    try:
        parser = argparse.ArgumentParser(
            prog="ace", description="ACE - Autonomous Code Editor v0.1"
        )

        parser.add_argument(
            "--version", action="version", version=f"ACE v{__version__}"
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Enable verbose error output"
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
        parser_apply.add_argument(
            "--force", action="store_true", help="Skip git safety checks (allows dirty tree)"
        )
        parser_apply.add_argument(
            "--stash", action="store_true", help="Stash git changes before applying"
        )
        parser_apply.add_argument(
            "--commit", action="store_true", help="Commit changes after applying"
        )
        parser_apply.set_defaults(func=cmd_apply)

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
