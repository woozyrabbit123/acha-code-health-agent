"""Patcher utility for generating and applying diffs"""

import difflib
import shutil
from pathlib import Path


class Patcher:
    """Handles diff generation and application"""

    def __init__(self, dist_dir: str = "dist", workdir: str = "workdir"):
        """
        Initialize patcher.

        Args:
            dist_dir: Directory to store patches
            workdir: Working directory for applying patches
        """
        self.dist_dir = Path(dist_dir)
        self.workdir = Path(workdir)

    def prepare_workdir(self, source_dir: str):
        """
        Prepare working directory by copying source files.

        Args:
            source_dir: Source directory to copy from
        """
        source_path = Path(source_dir)
        if not source_path.exists():
            raise ValueError(f"Source directory does not exist: {source_dir}")

        # Clear and recreate workdir
        if self.workdir.exists():
            shutil.rmtree(self.workdir)
        shutil.copytree(source_path, self.workdir)

    def generate_diff(self, original_content: str, modified_content: str, file_path: str) -> str:
        """
        Generate unified diff between original and modified content.

        Args:
            original_content: Original file content
            modified_content: Modified file content
            file_path: Path to the file (for diff headers)

        Returns:
            Unified diff string
        """
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = modified_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )

        return "".join(diff)

    def write_patch(self, diff_content: str, patch_filename: str = "patch.diff"):
        """
        Write diff to patch file in dist directory.

        Args:
            diff_content: Unified diff content
            patch_filename: Name of patch file
        """
        self.dist_dir.mkdir(exist_ok=True)
        patch_path = self.dist_dir / patch_filename

        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(diff_content)

    def apply_modifications(self, modifications: dict[str, str]):
        """
        Apply modifications to files in workdir.

        Args:
            modifications: Dictionary mapping file paths to new content
        """
        for file_path, new_content in modifications.items():
            target_file = self.workdir / file_path
            target_file.parent.mkdir(parents=True, exist_ok=True)

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(new_content)

    def count_diff_stats(self, diff_content: str) -> tuple[int, int]:
        """
        Count lines added and removed from a diff.

        Args:
            diff_content: Unified diff content

        Returns:
            Tuple of (lines_added, lines_removed)
        """
        lines_added = 0
        lines_removed = 0

        for line in diff_content.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1

        return lines_added, lines_removed
