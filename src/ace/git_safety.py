"""Git safety checks for apply operations."""

import subprocess
from pathlib import Path
from typing import Literal

from ace.errors import PolicyDenyError


def is_git_repo(path: Path) -> bool:
    """
    Check if path is inside a git repository.

    Args:
        path: Directory or file path to check

    Returns:
        True if path is in a git repository

    Examples:
        >>> is_git_repo(Path("/some/git/repo"))
        True  # if it's a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path if path.is_dir() else path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def get_git_status(path: Path) -> dict[str, list[str]]:
    """
    Get git status of repository.

    Args:
        path: Path inside git repository

    Returns:
        Dict with 'staged', 'unstaged', 'untracked' file lists

    Examples:
        >>> status = get_git_status(Path("/repo"))
        >>> status['unstaged']
        ['modified_file.py']
    """
    try:
        cwd = path if path.is_dir() else path.parent

        # Get status in porcelain format
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )

        staged = []
        unstaged = []
        untracked = []

        for line in result.stdout.splitlines():
            if not line:
                continue

            status_code = line[:2]
            filename = line[3:].strip()

            # First character is staged status, second is unstaged
            if status_code[0] != " " and status_code[0] != "?":
                staged.append(filename)
            if status_code[1] != " " and status_code[1] != "?":
                unstaged.append(filename)
            if status_code == "??":
                untracked.append(filename)

        return {
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        }

    except Exception:
        return {"staged": [], "unstaged": [], "untracked": []}


def is_git_tree_clean(path: Path, allow_untracked: bool = True) -> bool:
    """
    Check if git working tree is clean.

    Args:
        path: Path inside git repository
        allow_untracked: If True, untracked files don't count as dirty

    Returns:
        True if working tree is clean

    Examples:
        >>> is_git_tree_clean(Path("/repo"))
        True  # if no uncommitted changes
    """
    if not is_git_repo(path):
        return True  # Not a git repo, consider it "clean"

    status = get_git_status(path)

    # Staged or unstaged files make tree dirty
    if status["staged"] or status["unstaged"]:
        return False

    # Untracked files optionally make tree dirty
    if not allow_untracked and status["untracked"]:
        return False

    return True


def check_git_safety(
    path: Path,
    force: bool = False,
    allow_dirty: bool = False,
) -> None:
    """
    Check git safety before applying changes.

    Raises PolicyDenyError if:
    - Git tree is dirty and force=False and allow_dirty=False

    Args:
        path: Path to check
        force: If True, skip all safety checks
        allow_dirty: If True, allow dirty git tree

    Raises:
        PolicyDenyError: If safety check fails

    Examples:
        >>> check_git_safety(Path("/repo"), force=False)
        # Raises if dirty tree
    """
    if force:
        return  # Skip all checks when forced

    if not is_git_repo(path):
        return  # Not a git repo, nothing to check

    if not allow_dirty and not is_git_tree_clean(path, allow_untracked=True):
        status = get_git_status(path)
        dirty_files = status["staged"] + status["unstaged"]

        raise PolicyDenyError(
            f"Git working tree has uncommitted changes in {len(dirty_files)} file(s). "
            f"Commit changes first or use --force to override. "
            f"Dirty files: {', '.join(dirty_files[:5])}"
            + ("..." if len(dirty_files) > 5 else "")
        )


def git_stash_changes(path: Path, message: str = "ACE auto-stash") -> bool:
    """
    Stash current git changes.

    Args:
        path: Path inside git repository
        message: Stash message

    Returns:
        True if stash successful

    Examples:
        >>> git_stash_changes(Path("/repo"))
        True
    """
    try:
        cwd = path if path.is_dir() else path.parent

        result = subprocess.run(
            ["git", "stash", "push", "-m", message],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )

        return result.returncode == 0

    except Exception:
        return False


def git_commit_changes(
    path: Path,
    message: str,
    files: list[str] | None = None,
) -> bool:
    """
    Commit changes to git.

    Args:
        path: Path inside git repository
        message: Commit message
        files: Optional list of specific files to commit (None = all)

    Returns:
        True if commit successful

    Examples:
        >>> git_commit_changes(Path("/repo"), "fix: apply ACE refactorings")
        True
    """
    try:
        cwd = path if path.is_dir() else path.parent

        # Add files
        if files:
            for file in files:
                subprocess.run(
                    ["git", "add", file],
                    cwd=cwd,
                    capture_output=True,
                    check=True,
                )
        else:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=cwd,
                capture_output=True,
                check=True,
            )

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )

        return result.returncode == 0

    except Exception:
        return False
