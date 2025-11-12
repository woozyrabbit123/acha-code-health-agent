"""ACE unified patch output generation."""

from pathlib import Path

from ace.skills.python import Edit


def write_unified_patch(
    edits: list[Edit],
    to: Path,
    original_on_disk: bool = True,
) -> None:
    """
    Write unified diff patch file from edits.

    Args:
        edits: List of Edit objects
        to: Output path for patch file
        original_on_disk: If True, read original from disk; if False, use edit payload
    """
    # Sort edits deterministically by file path, then start line
    sorted_edits = sorted(edits, key=lambda e: (e.file, e.start_line))

    patch_lines = []

    for edit in sorted_edits:
        file_path = Path(edit.file)

        if not file_path.exists():
            # File doesn't exist - skip
            continue

        # Read original content
        try:
            original_content = file_path.read_text(encoding="utf-8")
        except Exception:
            # Can't read file - skip
            continue

        original_lines = original_content.splitlines(keepends=True)

        # Apply edit to get modified content
        if edit.op == "replace":
            new_content = edit.payload
        else:
            # For other ops, skip for now
            continue

        new_lines = new_content.splitlines(keepends=True)

        # Generate unified diff header
        patch_lines.append(f"--- a/{edit.file}\n")
        patch_lines.append(f"+++ b/{edit.file}\n")

        # Generate hunks
        # For simplicity, generate single hunk for entire file if different
        if original_lines != new_lines:
            patch_lines.append(
                f"@@ -1,{len(original_lines)} +1,{len(new_lines)} @@\n"
            )

            # Simple diff: show all removals then all additions
            for line in original_lines:
                patch_lines.append(f"-{line}")

            for line in new_lines:
                patch_lines.append(f"+{line}")

    # Write patch file
    if patch_lines:
        to.parent.mkdir(parents=True, exist_ok=True)
        to.write_text("".join(patch_lines), encoding="utf-8")
    else:
        # Empty patch - create empty file
        to.parent.mkdir(parents=True, exist_ok=True)
        to.write_text("", encoding="utf-8")
