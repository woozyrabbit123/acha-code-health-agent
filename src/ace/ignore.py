"""ACE ignore system - .aceignore file support."""

import re
from pathlib import Path


class IgnoreSpec:
    """Specification for ignoring files based on patterns."""

    def __init__(self, patterns: list[str]):
        """
        Initialize ignore spec with patterns.

        Args:
            patterns: List of glob or regex patterns
        """
        self.patterns = sorted(patterns)  # Deterministic evaluation
        self.compiled_patterns = []

        for pattern in self.patterns:
            if pattern.startswith("re:") and pattern.endswith("$"):
                # Anchored regex pattern: re:^.*_test\.py$
                regex_str = pattern[3:]  # Remove "re:" prefix
                self.compiled_patterns.append(("regex", re.compile(regex_str)))
            else:
                # Glob pattern - convert to regex
                regex_str = self._glob_to_regex(pattern)
                self.compiled_patterns.append(("glob", re.compile(regex_str)))

    def _glob_to_regex(self, pattern: str) -> str:
        """Convert glob pattern to regex."""
        # Escape special regex chars except * and ?
        pattern = pattern.replace("\\", "\\\\")
        pattern = pattern.replace(".", "\\.")
        pattern = pattern.replace("+", "\\+")
        pattern = pattern.replace("^", "\\^")
        pattern = pattern.replace("$", "\\$")
        pattern = pattern.replace("(", "\\(")
        pattern = pattern.replace(")", "\\)")
        pattern = pattern.replace("[", "\\[")
        pattern = pattern.replace("]", "\\]")
        pattern = pattern.replace("{", "\\{")
        pattern = pattern.replace("}", "\\}")
        pattern = pattern.replace("|", "\\|")

        # Convert glob wildcards to regex
        pattern = pattern.replace("**", "<<<DOUBLESTAR>>>")
        pattern = pattern.replace("*", "[^/]*")
        pattern = pattern.replace("<<<DOUBLESTAR>>>", ".*")
        pattern = pattern.replace("?", "[^/]")

        # Anchor pattern
        if not pattern.startswith("/"):
            # Match anywhere in path
            pattern = ".*" + pattern
        else:
            # Match from root
            pattern = "^" + pattern[1:]

        if not pattern.endswith("$"):
            pattern = pattern + "$"

        return pattern

    def match(self, path: Path) -> bool:
        """
        Check if path matches any ignore pattern.

        Args:
            path: Path to check

        Returns:
            True if path should be ignored
        """
        path_str = str(path).replace("\\", "/")  # Normalize for Windows

        for pattern_type, compiled in self.compiled_patterns:
            if compiled.match(path_str):
                return True

        return False


def load_aceignore(root: Path) -> IgnoreSpec | None:
    """
    Load .aceignore file from project root.

    Args:
        root: Project root directory

    Returns:
        IgnoreSpec if .aceignore exists, None otherwise
    """
    aceignore_path = root / ".aceignore"

    if not aceignore_path.exists():
        return None

    try:
        content = aceignore_path.read_text(encoding="utf-8")
        patterns = []

        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            patterns.append(line)

        if not patterns:
            return None

        return IgnoreSpec(patterns)

    except Exception:
        # If we can't read the file, return None
        return None
