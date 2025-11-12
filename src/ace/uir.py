"""UIR - Unified Issue Record schema for cross-tool findings."""

import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Severity levels for UIR findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(slots=True, frozen=True)
class UnifiedIssue:
    """
    Unified Issue Record for standardized findings across languages.

    Attributes:
        file: Source file path (relative or absolute)
        line: Line number where issue was found
        rule: Rule identifier (e.g., "unused-import", "missing-docstring")
        severity: Severity level (critical/high/medium/low/info)
        message: Human-readable issue description
        suggestion: Optional fix suggestion
        snippet: Code snippet showing the issue (for stable_id)
    """

    file: str
    line: int
    rule: str
    severity: Severity
    message: str
    suggestion: str = ""
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        """
        Convert UIR to JSON-serializable dictionary.

        Returns:
            Dictionary with all UIR fields
        """
        return {
            "file": self.file,
            "line": self.line,
            "rule": self.rule,
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "snippet": self.snippet,
            "stable_id": stable_id(self.file, self.rule, self.snippet),
        }


def stable_id(file: str, rule: str, snippet: str) -> str:
    """
    Generate deterministic stable ID for a UIR finding.

    Uses CRC32 hashing to create a compact, reproducible identifier.
    Format: <file_crc32>-<rule_crc32>-<snippet_crc32>

    Args:
        file: Source file path
        rule: Rule identifier
        snippet: Code snippet

    Returns:
        Stable ID as hex string (e.g., "a1b2c3d4-e5f6a7b8-c9d0e1f2")

    Examples:
        >>> stable_id("test.py", "unused-import", "import os")
        'f8e7d6c5-a1b2c3d4-e5f6a7b8'
    """
    file_crc = zlib.crc32(file.encode("utf-8")) & 0xFFFFFFFF
    rule_crc = zlib.crc32(rule.encode("utf-8")) & 0xFFFFFFFF
    snippet_crc = zlib.crc32(snippet.encode("utf-8")) & 0xFFFFFFFF

    return f"{file_crc:08x}-{rule_crc:08x}-{snippet_crc:08x}"


def create_uir(
    file: str,
    line: int,
    rule: str,
    severity: str | Severity,
    message: str,
    suggestion: str = "",
    snippet: str = "",
) -> UnifiedIssue:
    """
    Create a Unified Issue Record.

    Args:
        file: Source file path
        line: Line number
        rule: Rule identifier
        severity: Severity level (string or Severity enum)
        message: Issue description
        suggestion: Optional fix suggestion
        snippet: Code snippet for stable_id generation

    Returns:
        UnifiedIssue instance

    Examples:
        >>> uir = create_uir("test.py", 42, "unused-import", "high", "Unused import 'os'")
        >>> uir.file
        'test.py'
        >>> uir.severity
        <Severity.HIGH: 'high'>
    """
    if isinstance(severity, str):
        severity = Severity(severity)

    return UnifiedIssue(
        file=file,
        line=line,
        rule=rule,
        severity=severity,
        message=message,
        suggestion=suggestion,
        snippet=snippet,
    )
