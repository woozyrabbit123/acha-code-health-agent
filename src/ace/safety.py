"""Safety mechanisms for refactoring (parse-after-edit, rollback)."""

import ast
import hashlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path


def verify_parse_py(source: str) -> bool:
    """
    Verify Python source code is syntactically valid.

    Uses ast.parse to check syntax without executing code.

    Args:
        source: Python source code as string

    Returns:
        True if parseable, False otherwise

    Examples:
        >>> verify_parse_py("x = 1 + 2")
        True
        >>> verify_parse_py("x = 1 +")
        False
        >>> verify_parse_py("def foo():\\n    pass")
        True
    """
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False
    except Exception:
        # Catch other parsing errors (encoding, etc.)
        return False


def content_hash(content: str) -> str:
    """
    Generate SHA256 hash of content with 'sha256:' prefix.

    Uses UTF-8 encoding and returns hex digest with prefix.

    Args:
        content: String content to hash

    Returns:
        Hash string with 'sha256:' prefix

    Examples:
        >>> content_hash("hello world")
        'sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
        >>> content_hash("")
        'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    """
    hash_obj = hashlib.sha256(content.encode("utf-8"))
    return f"sha256:{hash_obj.hexdigest()}"


def is_idempotent(
    transform: Callable[[str], str], content: str, normalize_newlines: bool = True
) -> bool:
    """
    Check if a transformation is idempotent.

    A transformation is idempotent if: f(f(x)) == f(x)

    Args:
        transform: Function that transforms content
        content: Input content to test
        normalize_newlines: If True, treat "a" and "a\\n" as equal (default: True)

    Returns:
        True if idempotent, False otherwise

    Examples:
        >>> def add_header(s): return "# Header\\n" + s if not s.startswith("# Header") else s
        >>> is_idempotent(add_header, "code")
        True
        >>> def always_append(s): return s + "x"
        >>> is_idempotent(always_append, "code")
        False
    """
    try:
        # Apply transformation once
        first_pass = transform(content)

        # Apply transformation again
        second_pass = transform(first_pass)

        # Normalize newlines if requested
        if normalize_newlines:
            first_pass = first_pass.rstrip("\n")
            second_pass = second_pass.rstrip("\n")

        return first_pass == second_pass
    except Exception:
        # If transformation fails, it's not idempotent
        return False


def verify_parseable(file_path: str, language: str) -> bool:
    """
    Verify that a file is syntactically valid after refactoring.

    Args:
        file_path: Path to file
        language: Language type (python, markdown, yaml, shell)

    Returns:
        True if parseable, False otherwise

    Examples:
        >>> # This is a stub - full implementation would check file syntax
        >>> verify_parseable("test.py", "python")
        True
    """
    path = Path(file_path)

    if not path.exists():
        return False

    if language == "python":
        try:
            with open(path, encoding="utf-8") as f:
                source = f.read()
            return verify_parse_py(source)
        except Exception:
            return False

    # For other languages, assume valid (stubs)
    # TODO: Add markdown, yaml, shell validation
    return True


def _fsync_dir(directory: Path) -> None:
    """
    Fsync directory to ensure rename is persisted.

    Best-effort operation (some platforms don't support directory fsync).

    Args:
        directory: Directory to fsync
    """
    try:
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        # Best-effort; some platforms don't support directory fsync.
        pass


def atomic_write(path: Path, content: bytes) -> None:
    """
    Atomically write content to file using temp + fsync + rename.

    Guarantees:
    - Partial writes are never visible
    - Original file remains intact until replacement is complete
    - Content is synced to disk before rename
    - Directory metadata is synced (best-effort)

    Args:
        path: Target file path
        content: Bytes to write

    Raises:
        OSError: If write or rename fails

    Examples:
        >>> from pathlib import Path
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     target = Path(tmpdir) / "test.txt"
        ...     atomic_write(target, b"hello world")
        ...     target.read_bytes()
        b'hello world'
    """
    # Ensure parent directory exists
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (for atomic rename)
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp"
    )

    try:
        # Write content
        os.write(fd, content)

        # Flush to disk
        os.fsync(fd)

        # Close file descriptor
        os.close(fd)
        fd = -1

        # Atomic replace (POSIX guarantees atomicity)
        os.replace(temp_path, path)

        # Fsync directory to ensure rename is persisted
        _fsync_dir(path.parent)

    except Exception:
        # Clean up temp file on failure
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise


def parse_after_edit_ok(path: Path) -> bool:
    """
    Verify file is syntactically valid after edit.

    Determines language from file extension and validates syntax.

    Args:
        path: Path to file to validate

    Returns:
        True if file parses successfully, False otherwise

    Examples:
        >>> from pathlib import Path
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     test_file = Path(tmpdir) / "test.py"
        ...     test_file.write_text("x = 1 + 2")
        ...     parse_after_edit_ok(test_file)
        ...     test_file.write_text("x = 1 +")
        ...     parse_after_edit_ok(test_file)
        9
        True
        7
        False
    """
    if not path.exists():
        return False

    # Determine language from extension
    suffix = path.suffix.lower()

    if suffix == ".py":
        return verify_parseable(str(path), "python")
    elif suffix in {".md", ".markdown"}:
        return verify_parseable(str(path), "markdown")
    elif suffix in {".yml", ".yaml"}:
        return verify_parseable(str(path), "yaml")
    elif suffix in {".sh", ".bash"}:
        return verify_parseable(str(path), "shell")
    else:
        # Unknown language - assume valid
        return True


def create_backup(target_path: str, backup_dir: str) -> str:
    """
    Create safety backup before applying changes.

    Args:
        target_path: Path to back up
        backup_dir: Backup directory

    Returns:
        Backup path

    Note:
        Stub implementation - returns empty string.
        Full implementation would copy files to backup directory.
    """
    return ""


def rollback(backup_path: str, target_path: str) -> bool:
    """
    Rollback to backup if refactoring fails.

    Args:
        backup_path: Backup directory
        target_path: Target to restore

    Returns:
        True if successful

    Note:
        Stub implementation - always returns True.
        Full implementation would restore from backup.
    """
    return True
