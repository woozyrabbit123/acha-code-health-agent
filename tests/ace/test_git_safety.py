"""Tests for git safety checks and operations."""

import subprocess
from pathlib import Path

import pytest

from ace.errors import PolicyDenyError
from ace.git_safety import (
    check_git_safety,
    get_git_status,
    git_commit_changes,
    git_stash_changes,
    is_git_repo,
    is_git_tree_clean,
)


def init_git_repo(path: Path) -> None:
    """Initialize a git repository with proper configuration."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=path,
        check=True,
        capture_output=True,
    )


class TestGitRepoDetection:
    """Test git repository detection."""

    def test_is_git_repo_in_valid_repo(self, tmp_path):
        """Test detection of valid git repository."""
        # Initialize git repo
        init_git_repo(tmp_path)

        assert is_git_repo(tmp_path) is True

    def test_is_git_repo_in_subdirectory(self, tmp_path):
        """Test detection in subdirectory of git repo."""
        # Initialize git repo
        init_git_repo(tmp_path)

        # Create subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Should detect parent repo
        assert is_git_repo(subdir) is True

    def test_is_git_repo_in_non_git_dir(self, tmp_path):
        """Test detection in non-git directory."""
        assert is_git_repo(tmp_path) is False

    def test_is_git_repo_with_file_path(self, tmp_path):
        """Test detection with file path (should check parent dir)."""
        # Initialize git repo
        init_git_repo(tmp_path)

        # Create a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Should detect repo from file's parent dir
        assert is_git_repo(test_file) is True


class TestGitStatus:
    """Test git status parsing."""

    def test_get_git_status_clean_repo(self, tmp_path):
        """Test status of clean repository."""
        # Initialize git repo with initial commit
        init_git_repo(tmp_path)

        # Create initial commit
        test_file = tmp_path / "initial.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        status = get_git_status(tmp_path)
        assert status["staged"] == []
        assert status["unstaged"] == []
        assert status["untracked"] == []

    def test_get_git_status_unstaged_changes(self, tmp_path):
        """Test status with unstaged modifications."""
        # Setup repo with initial commit
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Modify file
        test_file.write_text("modified")

        status = get_git_status(tmp_path)
        assert "test.txt" in status["unstaged"]
        assert status["staged"] == []
        assert status["untracked"] == []

    def test_get_git_status_staged_changes(self, tmp_path):
        """Test status with staged changes."""
        # Setup repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Modify and stage
        test_file.write_text("modified")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

        status = get_git_status(tmp_path)
        assert "test.txt" in status["staged"]
        assert status["unstaged"] == []
        assert status["untracked"] == []

    def test_get_git_status_untracked_files(self, tmp_path):
        """Test status with untracked files."""
        # Setup repo
        init_git_repo(tmp_path)

        # Create untracked file
        test_file = tmp_path / "untracked.txt"
        test_file.write_text("untracked")

        status = get_git_status(tmp_path)
        assert "untracked.txt" in status["untracked"]
        assert status["staged"] == []
        assert status["unstaged"] == []


class TestGitTreeClean:
    """Test git working tree cleanliness checks."""

    def test_is_git_tree_clean_with_clean_repo(self, tmp_path):
        """Test clean repository detection."""
        # Setup clean repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        assert is_git_tree_clean(tmp_path) is True

    def test_is_git_tree_clean_with_unstaged_changes(self, tmp_path):
        """Test detection of unstaged changes."""
        # Setup repo and make unstaged change
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Modify file
        test_file.write_text("modified")

        assert is_git_tree_clean(tmp_path) is False

    def test_is_git_tree_clean_with_untracked_allowed(self, tmp_path):
        """Test that untracked files don't make tree dirty by default."""
        # Setup repo
        init_git_repo(tmp_path)

        # Create initial commit
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Add untracked file
        untracked = tmp_path / "untracked.txt"
        untracked.write_text("untracked")

        # Should be clean with allow_untracked=True (default)
        assert is_git_tree_clean(tmp_path, allow_untracked=True) is True

    def test_is_git_tree_clean_with_untracked_disallowed(self, tmp_path):
        """Test that untracked files can make tree dirty if disallowed."""
        # Setup repo with untracked file
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        untracked = tmp_path / "untracked.txt"
        untracked.write_text("untracked")

        # Should be dirty with allow_untracked=False
        assert is_git_tree_clean(tmp_path, allow_untracked=False) is False

    def test_is_git_tree_clean_non_git_dir(self, tmp_path):
        """Test that non-git directories are considered clean."""
        # Non-git dir should be treated as "clean"
        assert is_git_tree_clean(tmp_path) is True


class TestCheckGitSafety:
    """Test git safety enforcement."""

    def test_check_git_safety_clean_repo(self, tmp_path):
        """Test safety check passes for clean repo."""
        # Setup clean repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Should not raise
        check_git_safety(tmp_path)

    def test_check_git_safety_dirty_repo_raises(self, tmp_path):
        """Test safety check raises for dirty repo."""
        # Setup dirty repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Make dirty
        test_file.write_text("modified")

        # Should raise PolicyDenyError
        with pytest.raises(PolicyDenyError) as exc_info:
            check_git_safety(tmp_path)

        assert "uncommitted changes" in str(exc_info.value.message).lower()

    def test_check_git_safety_force_bypasses_check(self, tmp_path):
        """Test --force flag bypasses safety check."""
        # Setup dirty repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        test_file.write_text("modified")

        # Should not raise with force=True
        check_git_safety(tmp_path, force=True)

    def test_check_git_safety_allow_dirty(self, tmp_path):
        """Test allow_dirty flag permits dirty tree."""
        # Setup dirty repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        test_file.write_text("modified")

        # Should not raise with allow_dirty=True
        check_git_safety(tmp_path, allow_dirty=True)

    def test_check_git_safety_non_git_dir(self, tmp_path):
        """Test safety check passes for non-git directories."""
        # Non-git dir should not raise
        check_git_safety(tmp_path)


class TestGitStash:
    """Test git stash operations."""

    def test_git_stash_changes_success(self, tmp_path):
        """Test successful stashing of changes."""
        # Setup dirty repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Make changes
        test_file.write_text("modified")

        # Stash should succeed
        result = git_stash_changes(tmp_path, message="test stash")
        assert result is True

        # Tree should now be clean
        assert is_git_tree_clean(tmp_path) is True

    def test_git_stash_clean_repo(self, tmp_path):
        """Test stashing with no changes."""
        # Setup clean repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Stash with no changes should succeed
        result = git_stash_changes(tmp_path)
        assert result is True


class TestGitCommit:
    """Test git commit operations."""

    def test_git_commit_changes_all_files(self, tmp_path):
        """Test committing all modified files."""
        # Setup repo with uncommitted changes
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Modify file
        test_file.write_text("modified")

        # Commit should succeed
        result = git_commit_changes(tmp_path, "test commit")
        assert result is True

        # Tree should be clean
        assert is_git_tree_clean(tmp_path) is True

    def test_git_commit_specific_files(self, tmp_path):
        """Test committing specific files."""
        # Setup repo
        init_git_repo(tmp_path)

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("initial1")
        file2.write_text("initial2")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Modify both files
        file1.write_text("modified1")
        file2.write_text("modified2")

        # Commit only file1
        result = git_commit_changes(tmp_path, "commit file1", files=["file1.txt"])
        assert result is True

        # file1 should be clean, file2 still dirty
        status = get_git_status(tmp_path)
        assert "file1.txt" not in status["unstaged"]
        assert "file2.txt" in status["unstaged"]

    def test_git_commit_with_new_file(self, tmp_path):
        """Test committing newly created file."""
        # Setup repo
        init_git_repo(tmp_path)

        initial = tmp_path / "initial.txt"
        initial.write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create new file
        new_file = tmp_path / "new.txt"
        new_file.write_text("new")

        # Commit new file
        result = git_commit_changes(tmp_path, "add new file", files=["new.txt"])
        assert result is True

        # Should be tracked now
        status = get_git_status(tmp_path)
        assert "new.txt" not in status["untracked"]


class TestGitSafetyIntegration:
    """Integration tests for git safety with kernel."""

    def test_apply_with_force_on_dirty_repo(self, tmp_path):
        """Test that apply --force works on dirty repository."""
        # Setup dirty repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Make dirty
        dirty_file = tmp_path / "dirty.py"
        dirty_file.write_text("dirty = 1\n")

        # Import and test kernel function
        from ace.kernel import run_apply

        # Should succeed with force=True
        exit_code, receipts = run_apply(tmp_path, force=True)
        assert exit_code == 0

    def test_apply_without_force_on_dirty_repo_fails(self, tmp_path):
        """Test that apply without force fails on dirty repository."""
        # Setup dirty repo
        init_git_repo(tmp_path)

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Make dirty
        test_file.write_text("x = 2\n")

        from ace.errors import ExitCode
        from ace.kernel import run_apply

        # Should return POLICY_DENY
        exit_code, receipts = run_apply(tmp_path, force=False)
        assert exit_code == ExitCode.POLICY_DENY
