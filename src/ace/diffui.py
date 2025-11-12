"""
Interactive Diff UI for ACE - Accept/reject changes per file.

Provides an interactive interface for reviewing and applying patches
on a per-file basis using rich for terminal UI.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import re


@dataclass
class FilePatch:
    """Represents a patch for a single file."""
    file_path: str
    old_content: Optional[str]
    new_content: str
    is_new_file: bool = False
    is_deleted: bool = False
    hunks: list[str] = None

    def __post_init__(self):
        if self.hunks is None:
            self.hunks = []


def parse_patch(patch_content: str) -> dict[str, FilePatch]:
    """
    Parse unified diff format into FilePatch objects.

    Args:
        patch_content: Unified diff content

    Returns:
        Dictionary mapping file paths to FilePatch objects
    """
    patches = {}
    current_file = None
    current_old = []
    current_new = []
    current_hunks = []

    lines = patch_content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # File header
        if line.startswith('--- '):
            # Save previous file if exists
            if current_file:
                patches[current_file] = FilePatch(
                    file_path=current_file,
                    old_content='\n'.join(current_old) if current_old else None,
                    new_content='\n'.join(current_new),
                    hunks=current_hunks
                )

            # Parse file path
            old_file = line[4:].strip()
            if i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
                new_file = lines[i + 1][4:].strip()
                i += 1

                # Normalize paths (remove a/ b/ prefixes)
                if old_file.startswith('a/'):
                    old_file = old_file[2:]
                if new_file.startswith('b/'):
                    new_file = new_file[2:]

                current_file = new_file
                current_old = []
                current_new = []
                current_hunks = []

        # Hunk header
        elif line.startswith('@@'):
            current_hunks.append(line)

        # Content lines
        elif line.startswith('-') and not line.startswith('---'):
            current_old.append(line[1:])
            current_hunks.append(line)
        elif line.startswith('+') and not line.startswith('+++'):
            current_new.append(line[1:])
            current_hunks.append(line)
        elif line.startswith(' '):
            # Context line
            current_old.append(line[1:])
            current_new.append(line[1:])
            current_hunks.append(line)

        i += 1

    # Save last file
    if current_file:
        patches[current_file] = FilePatch(
            file_path=current_file,
            old_content='\n'.join(current_old) if current_old else None,
            new_content='\n'.join(current_new),
            hunks=current_hunks
        )

    return patches


def parse_changes_dict(changes: dict[str, str]) -> dict[str, FilePatch]:
    """
    Parse changes dictionary into FilePatch objects.

    Args:
        changes: Dictionary mapping file paths to new content

    Returns:
        Dictionary mapping file paths to FilePatch objects
    """
    patches = {}
    for file_path, new_content in changes.items():
        path = Path(file_path)

        # Read old content if file exists
        old_content = None
        is_new_file = False
        if path.exists():
            try:
                old_content = path.read_text(encoding='utf-8')
            except Exception:
                old_content = None
        else:
            is_new_file = True

        patches[file_path] = FilePatch(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            is_new_file=is_new_file
        )

    return patches


def interactive_review(
    changes: dict[str, str],
    auto_approve: bool = False
) -> set[str]:
    """
    Interactively review and approve/reject changes per file.

    Args:
        changes: Dictionary mapping file paths to new content
        auto_approve: If True, automatically approve all changes

    Returns:
        Set of approved file paths
    """
    if not changes:
        return set()

    # Parse changes into FilePatch objects
    patches = parse_changes_dict(changes)

    if auto_approve:
        return set(patches.keys())

    # Try to import rich for nice UI
    try:
        from rich.console import Console
        from rich.syntax import Syntax
        from rich.panel import Panel
        from rich.prompt import Prompt
        use_rich = True
        console = Console()
    except ImportError:
        use_rich = False
        console = None

    approved = set()

    for file_path, patch in patches.items():
        # Display file info
        if use_rich:
            _display_patch_rich(console, file_path, patch)
        else:
            _display_patch_plain(file_path, patch)

        # Prompt for decision
        while True:
            if use_rich:
                choice = Prompt.ask(
                    "\n[bold cyan]Action[/bold cyan]",
                    choices=["a", "r", "v", "q"],
                    default="a"
                )
            else:
                choice = input("\nAction [a]ccept / [r]eject / [v]iew / [q]uit (default: a): ").strip().lower()
                if not choice:
                    choice = 'a'

            if choice == 'a':
                approved.add(file_path)
                if use_rich:
                    console.print(f"[green]✓[/green] Approved: {file_path}")
                else:
                    print(f"✓ Approved: {file_path}")
                break
            elif choice == 'r':
                if use_rich:
                    console.print(f"[red]✗[/red] Rejected: {file_path}")
                else:
                    print(f"✗ Rejected: {file_path}")
                break
            elif choice == 'v':
                # Show full diff
                if use_rich:
                    _display_full_diff_rich(console, patch)
                else:
                    _display_full_diff_plain(patch)
            elif choice == 'q':
                if use_rich:
                    console.print("\n[yellow]Review cancelled[/yellow]")
                else:
                    print("\nReview cancelled")
                return approved
            else:
                if use_rich:
                    console.print("[red]Invalid choice[/red]")
                else:
                    print("Invalid choice")

    return approved


def _display_patch_rich(console, file_path: str, patch: FilePatch) -> None:
    """Display patch info using rich."""
    status = "[green]NEW[/green]" if patch.is_new_file else "[yellow]MODIFIED[/yellow]"

    console.print(f"\n{'=' * 70}")
    console.print(f"{status} {file_path}")
    console.print(f"{'=' * 70}")

    # Show snippet
    lines = patch.new_content.split('\n')
    snippet = '\n'.join(lines[:20])
    if len(lines) > 20:
        snippet += f"\n... ({len(lines) - 20} more lines)"

    syntax = Syntax(snippet, "python", theme="monokai", line_numbers=True)
    console.print(syntax)


def _display_patch_plain(file_path: str, patch: FilePatch) -> None:
    """Display patch info using plain text."""
    status = "NEW" if patch.is_new_file else "MODIFIED"

    print(f"\n{'=' * 70}")
    print(f"{status} {file_path}")
    print(f"{'=' * 70}")

    # Show snippet
    lines = patch.new_content.split('\n')
    snippet = '\n'.join(lines[:20])
    if len(lines) > 20:
        snippet += f"\n... ({len(lines) - 20} more lines)"

    print(snippet)


def _display_full_diff_rich(console, patch: FilePatch) -> None:
    """Display full diff using rich."""
    if patch.old_content:
        old_lines = patch.old_content.split('\n')
        new_lines = patch.new_content.split('\n')

        # Simple line-by-line diff
        console.print("\n[bold]Full Diff:[/bold]")
        max_lines = max(len(old_lines), len(new_lines))

        for i in range(max_lines):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""

            if old_line != new_line:
                if old_line:
                    console.print(f"[red]- {old_line}[/red]")
                if new_line:
                    console.print(f"[green]+ {new_line}[/green]")
    else:
        syntax = Syntax(patch.new_content, "python", theme="monokai", line_numbers=True)
        console.print(syntax)


def _display_full_diff_plain(patch: FilePatch) -> None:
    """Display full diff using plain text."""
    if patch.old_content:
        old_lines = patch.old_content.split('\n')
        new_lines = patch.new_content.split('\n')

        print("\nFull Diff:")
        max_lines = max(len(old_lines), len(new_lines))

        for i in range(max_lines):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""

            if old_line != new_line:
                if old_line:
                    print(f"- {old_line}")
                if new_line:
                    print(f"+ {new_line}")
    else:
        print(patch.new_content)


def apply_approved_changes(
    changes: dict[str, str],
    approved: set[str],
    dry_run: bool = False
) -> dict[str, bool]:
    """
    Apply approved changes to files.

    Args:
        changes: Dictionary mapping file paths to new content
        approved: Set of approved file paths
        dry_run: If True, don't actually write files

    Returns:
        Dictionary mapping file paths to success status
    """
    results = {}

    for file_path in approved:
        if file_path not in changes:
            results[file_path] = False
            continue

        if dry_run:
            results[file_path] = True
            continue

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(changes[file_path], encoding='utf-8')
            results[file_path] = True
        except Exception as e:
            results[file_path] = False

    return results


def batch_review(
    changes: dict[str, str],
    filters: Optional[list[str]] = None
) -> set[str]:
    """
    Review changes with filtering.

    Args:
        changes: Dictionary mapping file paths to new content
        filters: Optional list of file patterns to include

    Returns:
        Set of approved file paths
    """
    if filters:
        # Filter changes by patterns
        filtered_changes = {}
        for file_path, content in changes.items():
            if any(pattern in file_path for pattern in filters):
                filtered_changes[file_path] = content
    else:
        filtered_changes = changes

    return interactive_review(filtered_changes)
