"""Smoke tests for the ACE CLI scaffold."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _build_env() -> dict[str, str]:
    """Construct an environment that exposes the source tree."""
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent.parent / "src"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{existing}:{src_path}" if existing else str(src_path)
    return env


@pytest.mark.parametrize("command", ["analyze", "refactor", "validate", "export", "apply"])
def test_cli_help_lists_subcommands(command: str) -> None:
    """Ensure the CLI help output includes each expected subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "ace.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=_build_env(),
    )

    assert result.returncode == 0
    assert command in result.stdout


def test_cli_version_command() -> None:
    """Ensure the ACE CLI reports the scaffold version."""
    ace_executable = shutil.which("ace")
    if ace_executable is not None:
        cmd = [ace_executable, "--version"]
    else:
        cmd = [sys.executable, "-m", "ace.cli", "--version"]

    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        env=_build_env(),
    )

    assert result.returncode == 0
    assert "ACE v0.1.0-dev" in result.stdout
