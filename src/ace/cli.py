"""Command-line interface scaffolding for ACE v0.1.

TODO: Replace stubs with fully featured CLI implementations.
"""
from __future__ import annotations

import argparse
import sys
from typing import Iterable

from . import __version__


def _add_subcommand(parser: argparse._SubParsersAction[argparse.ArgumentParser], name: str) -> None:
    """Register a stub subcommand that echoes its invocation."""
    command_parser = parser.add_parser(name, help=f"Run the ACE {name} stage.")
    command_parser.set_defaults(command=name)


def _handle_command(command: str | None) -> int:
    """Print a stub message for the requested command."""
    if command is None:
        return 1
    print(f"ACE v0.1 stub: {command}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the ACE CLI."""
    parser = argparse.ArgumentParser(description="ACE v0.1 command-line interface stubs.")
    parser.add_argument("--version", action="version", version=f"ACE v{__version__}")

    subparsers = parser.add_subparsers(dest="command", required=False, title="commands")

    for command_name in ("analyze", "refactor", "validate", "export", "apply"):
        _add_subcommand(subparsers, command_name)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point for the ACE CLI."""
    parser = build_parser()
    parsed = parser.parse_args(list(argv) if argv is not None else None)

    if parsed.command is None:
        parser.print_help()
        return 0

    return _handle_command(parsed.command)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
