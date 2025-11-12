"""ACE style rules for code hygiene (auto-fix, text-level)."""

from ace.skills.python import Edit, EditPlan
from ace.uir import UnifiedIssue, create_uir, stable_id


def analyze_trailing_whitespace(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze for trailing whitespace (PY-S310-TRAILING-WS).

    Args:
        src: Source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    findings = []
    lines = src.splitlines(keepends=True)

    for line_num, line in enumerate(lines, start=1):
        # Check for trailing whitespace (excluding newline)
        line_without_newline = line.rstrip("\r\n")
        if line_without_newline and line_without_newline != line_without_newline.rstrip():
            finding = create_uir(
                file=path,
                line=line_num,
                rule="PY-S310-TRAILING-WS",
                severity="low",
                message="trailing whitespace",
                suggestion="Remove trailing whitespace",
                snippet=line_without_newline[:50],
            )
            findings.append(finding)

    return findings


def refactor_trailing_whitespace(
    src: str, path: str, findings: list[UnifiedIssue]
) -> tuple[str, EditPlan]:
    """
    Remove trailing whitespace (PY-S310-TRAILING-WS).

    Args:
        src: Original source code
        path: File path
        findings: List of findings

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    lines = src.splitlines(keepends=True)
    modified = False
    new_lines = []

    for line in lines:
        # Remove trailing whitespace but preserve line endings
        line_without_newline = line.rstrip("\r\n")
        line_ending = line[len(line_without_newline) :]

        stripped = line_without_newline.rstrip()

        if stripped != line_without_newline:
            modified = True

        new_lines.append(stripped + line_ending)

    new_code = "".join(new_lines)

    edit = Edit(
        file=path,
        start_line=1,
        end_line=len(lines),
        op="replace",
        payload=new_code,
    )

    plan = EditPlan(
        id=stable_id(path, "PY-S310-TRAILING-WS", "plan"),
        findings=findings,
        edits=[edit] if modified else [],
        invariants=["must_parse"],
        estimated_risk=0.1,
    )

    return new_code, plan


def analyze_eof_newline(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze for missing EOF newline (PY-S311-EOF-NL).

    Args:
        src: Source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    findings = []

    if not src:
        return findings

    # Check if file ends with exactly one newline
    if not src.endswith("\n"):
        finding = create_uir(
            file=path,
            line=len(src.splitlines()),
            rule="PY-S311-EOF-NL",
            severity="low",
            message="missing newline at end of file",
            suggestion="Add newline at EOF",
            snippet="<EOF>",
        )
        findings.append(finding)
    elif src.endswith("\n\n"):
        # Multiple newlines at EOF
        finding = create_uir(
            file=path,
            line=len(src.splitlines()),
            rule="PY-S311-EOF-NL",
            severity="low",
            message="multiple newlines at end of file",
            suggestion="Ensure exactly one newline at EOF",
            snippet="<EOF>",
        )
        findings.append(finding)

    return findings


def refactor_eof_newline(
    src: str, path: str, findings: list[UnifiedIssue]
) -> tuple[str, EditPlan]:
    """
    Fix EOF newline (PY-S311-EOF-NL).

    Args:
        src: Original source code
        path: File path
        findings: List of findings

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    if not src:
        return src, EditPlan(
            id=stable_id(path, "PY-S311-EOF-NL", "plan"),
            findings=[],
            edits=[],
            invariants=[],
            estimated_risk=0.0,
        )

    # Ensure exactly one newline at EOF
    new_code = src.rstrip("\n") + "\n"

    modified = new_code != src

    edit = Edit(
        file=path,
        start_line=1,
        end_line=len(src.splitlines()),
        op="replace",
        payload=new_code,
    )

    plan = EditPlan(
        id=stable_id(path, "PY-S311-EOF-NL", "plan"),
        findings=findings,
        edits=[edit] if modified else [],
        invariants=["must_parse"],
        estimated_risk=0.1,
    )

    return new_code, plan


def analyze_excessive_blanklines(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze for excessive blank lines (PY-S312-BLANKLINES).

    Args:
        src: Source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    findings = []
    lines = src.splitlines(keepends=True)

    consecutive_blanks = 0
    first_blank_line = 0

    for line_num, line in enumerate(lines, start=1):
        # Check if line is blank (only whitespace)
        if line.strip() == "":
            if consecutive_blanks == 0:
                first_blank_line = line_num
            consecutive_blanks += 1
        else:
            if consecutive_blanks >= 3:
                finding = create_uir(
                    file=path,
                    line=first_blank_line,
                    rule="PY-S312-BLANKLINES",
                    severity="low",
                    message=f"{consecutive_blanks} consecutive blank lines",
                    suggestion="Collapse to 1 blank line",
                    snippet="<blank lines>",
                )
                findings.append(finding)

            consecutive_blanks = 0

    return findings


def refactor_excessive_blanklines(
    src: str, path: str, findings: list[UnifiedIssue]
) -> tuple[str, EditPlan]:
    """
    Collapse excessive blank lines (PY-S312-BLANKLINES).

    Args:
        src: Original source code
        path: File path
        findings: List of findings

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    lines = src.splitlines(keepends=True)

    new_lines = []
    consecutive_blanks = 0
    modified = False

    for line in lines:
        # Check if line is blank
        if line.strip() == "":
            consecutive_blanks += 1
            if consecutive_blanks <= 1:
                new_lines.append(line)
            else:
                modified = True
        else:
            new_lines.append(line)
            consecutive_blanks = 0

    new_code = "".join(new_lines)

    edit = Edit(
        file=path,
        start_line=1,
        end_line=len(lines),
        op="replace",
        payload=new_code,
    )

    plan = EditPlan(
        id=stable_id(path, "PY-S312-BLANKLINES", "plan"),
        findings=findings,
        edits=[edit] if modified else [],
        invariants=["must_parse"],
        estimated_risk=0.1,
    )

    return new_code, plan
