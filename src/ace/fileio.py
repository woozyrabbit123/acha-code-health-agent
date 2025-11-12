"""File I/O utilities with robust encoding and newline handling."""

import os
from pathlib import Path
from typing import Literal


def detect_newline_style(content: str) -> Literal["LF", "CRLF", "CR", "MIXED"]:
    """
    Detect the newline style used in text content.

    Args:
        content: Text content to analyze

    Returns:
        Newline style: "LF" (Unix), "CRLF" (Windows), "CR" (old Mac), or "MIXED"

    Examples:
        >>> detect_newline_style("line1\\nline2\\n")
        'LF'
        >>> detect_newline_style("line1\\r\\nline2\\r\\n")
        'CRLF'
    """
    # Count different newline types
    # For mixed detection, need to check for standalone LF, CR, and CRLF
    has_crlf = "\r\n" in content

    # Check for standalone LF (not part of CRLF)
    has_standalone_lf = False
    for i, char in enumerate(content):
        if char == "\n" and (i == 0 or content[i - 1] != "\r"):
            has_standalone_lf = True
            break

    # Check for standalone CR (not part of CRLF)
    has_standalone_cr = False
    for i, char in enumerate(content):
        if char == "\r" and (i == len(content) - 1 or content[i + 1] != "\n"):
            has_standalone_cr = True
            break

    # Count distinct styles
    styles = sum([has_crlf, has_standalone_lf, has_standalone_cr])

    if styles == 0:
        return "LF"  # Default for files with no newlines
    if styles > 1:
        return "MIXED"
    if has_crlf:
        return "CRLF"
    if has_standalone_lf:
        return "LF"
    return "CR"


def normalize_newlines(content: str, target_style: Literal["LF", "CRLF"] = "LF") -> str:
    """
    Normalize all newlines to a consistent style.

    Args:
        content: Text content with potentially mixed newlines
        target_style: Target newline style (default: LF for Unix)

    Returns:
        Content with normalized newlines

    Examples:
        >>> normalize_newlines("line1\\r\\nline2\\n", "LF")
        'line1\\nline2\\n'
        >>> normalize_newlines("line1\\nline2\\n", "CRLF")
        'line1\\r\\nline2\\r\\n'
    """
    # First normalize to LF
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")

    # Then convert to target
    if target_style == "CRLF":
        return normalized.replace("\n", "\r\n")
    return normalized


def read_text_file(file_path: Path | str, preserve_newlines: bool = True) -> tuple[str, str]:
    """
    Read text file with robust encoding and newline handling.

    Uses utf-8 encoding with surrogateescape error handler to handle
    files with encoding issues. Detects and optionally preserves original
    newline style for deterministic round-trips.

    Args:
        file_path: Path to file to read
        preserve_newlines: If True, detect original newline style

    Returns:
        Tuple of (content, original_newline_style)
        Content has normalized LF newlines for processing.
        Original style is "LF", "CRLF", "CR", or "MIXED".

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read

    Examples:
        >>> # Reading a Windows file
        >>> content, style = read_text_file("windows.txt")
        >>> style
        'CRLF'
        >>> "\\n" in content  # Content normalized to LF
        True
    """
    path = Path(file_path)

    # Read file in binary mode to preserve exact bytes
    with open(path, "rb") as f:
        raw_bytes = f.read()

    # Decode with surrogateescape to handle encoding errors
    content = raw_bytes.decode("utf-8", errors="surrogateescape")

    # Detect original newline style before normalization
    original_style = detect_newline_style(content) if preserve_newlines else "LF"

    # Normalize to LF for internal processing
    normalized_content = normalize_newlines(content, "LF")

    return normalized_content, original_style


def write_text_file(
    file_path: Path | str,
    content: str,
    newline_style: Literal["LF", "CRLF"] | None = None,
    create_dirs: bool = False,
) -> None:
    """
    Write text file with specified newline style.

    Uses utf-8 encoding with surrogateescape for round-trip safety.
    Can preserve original newline style or force a specific style.

    Args:
        file_path: Path to write
        content: Text content (should have LF newlines internally)
        newline_style: Target newline style (None = use system default)
        create_dirs: If True, create parent directories

    Raises:
        PermissionError: If file can't be written
        OSError: If directory creation fails

    Examples:
        >>> write_text_file("output.txt", "line1\\nline2\\n", newline_style="CRLF")
        >>> # File written with CRLF line endings
    """
    path = Path(file_path)

    # Create parent directories if requested
    if create_dirs and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    # Convert newlines if style specified
    if newline_style == "CRLF":
        output_content = normalize_newlines(content, "CRLF")
    elif newline_style == "LF":
        output_content = normalize_newlines(content, "LF")
    else:
        # Use system default (LF on Unix, CRLF on Windows)
        output_content = content.replace("\n", os.linesep)

    # Encode and write
    raw_bytes = output_content.encode("utf-8", errors="surrogateescape")

    with open(path, "wb") as f:
        f.write(raw_bytes)


def read_text_preserving_style(file_path: Path | str) -> tuple[str, str]:
    """
    Read file and detect newline style for round-trip preservation.

    Convenience function that always preserves newline style.

    Args:
        file_path: Path to read

    Returns:
        Tuple of (content_with_LF_newlines, original_style)

    Examples:
        >>> content, style = read_text_preserving_style("file.txt")
        >>> # Later: write_text_file("file.txt", modified, newline_style=style)
    """
    return read_text_file(file_path, preserve_newlines=True)


def write_text_preserving_style(
    file_path: Path | str, content: str, original_style: str
) -> None:
    """
    Write file preserving original newline style.

    Convenience function for round-trip preservation.

    Args:
        file_path: Path to write
        content: Content with LF newlines
        original_style: Original newline style ("LF", "CRLF", etc.)

    Examples:
        >>> content, style = read_text_preserving_style("file.txt")
        >>> modified = content.replace("old", "new")
        >>> write_text_preserving_style("file.txt", modified, style)
    """
    if original_style == "MIXED":
        # For mixed newlines, default to LF
        target_style: Literal["LF", "CRLF"] = "LF"
    elif original_style in ("LF", "CR"):
        target_style = "LF"
    else:  # CRLF
        target_style = "CRLF"

    write_text_file(file_path, content, newline_style=target_style)
