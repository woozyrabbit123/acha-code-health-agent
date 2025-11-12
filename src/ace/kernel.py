"""ACE Kernel - Orchestrates analysis, refactoring, and validation."""

import time
from pathlib import Path

from ace.errors import ExitCode
from ace.fileio import read_text_file, write_text_preserving_style
from ace.git_safety import check_git_safety, git_commit_changes, git_stash_changes
from ace.receipts import Receipt, create_receipt
from ace.safety import content_hash, is_idempotent
from ace.skills.config import analyze_yaml_duplicate_keys
from ace.skills.markdown import analyze_markdown_dangerous_commands
from ace.skills.python import (
    EditPlan,
    analyze_broad_except,
    analyze_import_sort,
    analyze_py,
    refactor_broad_except,
    refactor_import_sort,
    refactor_py_timeout,
    validate_python_syntax,
)
from ace.skills.shell import analyze_shell_strict_mode
from ace.uir import UnifiedIssue


def run_analyze(target_path: Path | str, rules: list[str] | None = None) -> list[UnifiedIssue]:
    """
    Run analysis on target path and collect findings.

    Args:
        target_path: Directory or file to analyze (Path or str)
        rules: Optional list of rule IDs to run (None = all rules)

    Returns:
        List of UnifiedIssue findings
    """
    all_findings = []

    # Convert str to Path if needed
    if isinstance(target_path, str):
        target_path = Path(target_path)

    # Normalize rules filter
    rules_filter = {r.upper() for r in rules} if rules else None

    def should_run_rule(rule_id: str) -> bool:
        """Check if rule should be run based on filter."""
        if rules_filter is None:
            return True
        return rule_id.upper() in rules_filter

    if target_path.is_file():
        files = [target_path]
    else:
        # Collect all files (sorted for determinism)
        files = sorted(target_path.rglob("*"))
        files = [f for f in files if f.is_file()]

    for file_path in files:
        try:
            # Use robust file I/O with encoding/newline handling
            content, _ = read_text_file(file_path, preserve_newlines=False)
            path_str = str(file_path)

            # Python rules
            if file_path.suffix == ".py":
                if should_run_rule("PY-S101-UNSAFE-HTTP"):
                    all_findings.extend(analyze_py(content, path_str))
                if should_run_rule("PY-E201-BROAD-EXCEPT"):
                    all_findings.extend(analyze_broad_except(content, path_str))
                if should_run_rule("PY-I101-IMPORT-SORT"):
                    all_findings.extend(analyze_import_sort(content, path_str))

            # Markdown rules
            elif file_path.suffix == ".md":
                if should_run_rule("MD-S001-DANGEROUS-COMMAND"):
                    all_findings.extend(
                        analyze_markdown_dangerous_commands(content, path_str)
                    )

            # YAML rules
            elif file_path.suffix in {".yml", ".yaml"}:
                if should_run_rule("YML-F001-DUPLICATE-KEY"):
                    all_findings.extend(analyze_yaml_duplicate_keys(content, path_str))

            # Shell rules
            elif file_path.suffix == ".sh" or (
                file_path.suffix == "" and content.startswith("#!")
            ):
                if should_run_rule("SH-S001-MISSING-STRICT-MODE"):
                    all_findings.extend(analyze_shell_strict_mode(content, path_str))

        except Exception:
            # Skip files that can't be read or analyzed
            pass

    # Sort findings for determinism
    all_findings.sort(key=lambda f: (f.file, f.line, f.rule))

    return all_findings


def run_refactor(
    target_path: Path, rules: list[str] | None = None
) -> list[EditPlan]:
    """
    Generate refactoring plans for findings.

    Args:
        target_path: Directory or file to refactor
        rules: Optional list of rule IDs to apply (None = all refactorable rules)

    Returns:
        List of EditPlan objects
    """
    # First, run analysis to get findings
    findings = run_analyze(target_path, rules)

    # Group findings by file and rule
    file_rule_findings = {}
    for finding in findings:
        key = (finding.file, finding.rule)
        if key not in file_rule_findings:
            file_rule_findings[key] = []
        file_rule_findings[key].append(finding)

    # Generate refactoring plans
    plans = []

    for (file_path_str, rule_id), rule_findings in file_rule_findings.items():
        try:
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue

            # Use robust file I/O with encoding/newline handling
            content, _ = read_text_file(file_path, preserve_newlines=False)

            # Apply appropriate refactoring based on rule
            if rule_id == "PY-S101-UNSAFE-HTTP":
                _, plan = refactor_py_timeout(content, file_path_str, rule_findings)
                if plan.edits:  # Only add if there are actual edits
                    plans.append(plan)

            elif rule_id == "PY-E201-BROAD-EXCEPT":
                _, plan = refactor_broad_except(content, file_path_str, rule_findings)
                if plan.edits:  # Only add if there are actual edits
                    plans.append(plan)

            elif rule_id == "PY-I101-IMPORT-SORT":
                _, plan = refactor_import_sort(content, file_path_str, rule_findings)
                if plan.edits:
                    plans.append(plan)

            # Detect-only rules (MD, YML, SH) don't generate refactoring plans

        except Exception:
            # Skip files that can't be refactored
            pass

    # Sort plans for determinism
    plans.sort(key=lambda p: p.id)

    return plans


def run_validate(target_path: Path, rules: list[str] | None = None) -> list[dict]:
    """
    Validate refactoring plans without applying them.

    Args:
        target_path: Directory or file to validate
        rules: Optional list of rule IDs to validate

    Returns:
        List of validation receipts
    """
    plans = run_refactor(target_path, rules)
    receipts = []

    for plan in plans:
        if not plan.edits:
            continue

        # For now, just check if the refactored code parses
        edit = plan.edits[0]  # Assume single edit per plan
        file_path = Path(edit.file)

        if not file_path.exists():
            continue

        try:
            # Check if refactored code is valid
            if file_path.suffix == ".py":
                parse_valid = validate_python_syntax(edit.payload)
            else:
                parse_valid = True

            # Calculate content hashes using robust file I/O
            before_content, _ = read_text_file(file_path, preserve_newlines=False)
            before_hash = content_hash(before_content)
            after_hash = content_hash(edit.payload)

            receipt = {
                "plan_id": plan.id,
                "file": edit.file,
                "parse_valid": parse_valid,
                "before_hash": before_hash,
                "after_hash": after_hash,
                "estimated_risk": plan.estimated_risk,
                "invariants_met": parse_valid,  # Simplified check
            }
            receipts.append(receipt)

        except Exception:
            # Skip validation errors
            pass

    return receipts


def run_apply(
    target_path: Path,
    rules: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    stash: bool = False,
    commit: bool = False,
) -> tuple[int, list[Receipt]]:
    """
    Apply refactoring plans to files with git safety checks.

    Args:
        target_path: Directory or file to apply changes to
        rules: Optional list of rule IDs to apply
        dry_run: If True, don't actually write files
        force: If True, skip git safety checks
        stash: If True, stash changes before applying
        commit: If True, commit changes after applying

    Returns:
        Tuple of (exit_code, receipts)
    """
    # Git safety checks
    try:
        check_git_safety(target_path, force=force, allow_dirty=False)
    except Exception:
        # If safety check fails, return policy deny
        return (ExitCode.POLICY_DENY, [])

    # Stash if requested
    if stash and not dry_run:
        git_stash_changes(target_path, message="ACE: stash before refactoring")

    plans = run_refactor(target_path, rules)

    if not plans:
        return (ExitCode.SUCCESS, [])

    modified_files = []
    receipts = []

    for plan in plans:
        if not plan.edits:
            continue

        edit = plan.edits[0]  # Assume single edit per plan
        file_path = Path(edit.file)

        if not file_path.exists():
            continue

        try:
            # Start timing
            start_time = time.perf_counter()

            # Read file preserving original newline style for round-trip
            original_content, original_newline_style = read_text_file(
                file_path, preserve_newlines=True
            )

            # Verify idempotency for Python files
            if file_path.suffix == ".py":

                # Create transform function for idempotency check
                def transform(
                    content: str,
                    fpath: str = edit.file,
                    p: EditPlan = plan,
                ) -> str:
                    # Re-run the refactoring
                    rule_id = p.findings[0].rule if p.findings else ""
                    if rule_id == "PY-E201-BROAD-EXCEPT":
                        refactored, _ = refactor_broad_except(content, fpath, [])
                        return refactored
                    elif rule_id == "PY-I101-IMPORT-SORT":
                        refactored, _ = refactor_import_sort(content, fpath, [])
                        return refactored
                    return content

                # Check idempotency
                idempotent = is_idempotent(transform, original_content)
            else:
                idempotent = True

            # Validate syntax if applicable
            if file_path.suffix == ".py":
                parse_valid = validate_python_syntax(edit.payload)
            else:
                parse_valid = True

            # Write the changes preserving original newline style
            if not dry_run:
                write_text_preserving_style(file_path, edit.payload, original_newline_style)
                modified_files.append(str(file_path))

            # Calculate duration
            end_time = time.perf_counter()
            duration_ms = int((end_time - start_time) * 1000)

            # Create receipt
            receipt = create_receipt(
                plan_id=plan.id,
                file_path=str(file_path),
                before_content=original_content,
                after_content=edit.payload,
                parse_valid=parse_valid,
                invariants_met=parse_valid and idempotent,
                estimated_risk=plan.estimated_risk,
                duration_ms=duration_ms,
            )
            receipts.append(receipt)

        except Exception:
            # Skip files that can't be written
            return (ExitCode.OPERATIONAL_ERROR, receipts)

    # Commit if requested and files were modified
    if commit and not dry_run and modified_files:
        rule_desc = f" ({', '.join(rules)})" if rules else ""
        commit_msg = f"refactor: apply ACE refactorings{rule_desc}"
        git_commit_changes(target_path, commit_msg, modified_files)

    return (ExitCode.SUCCESS, receipts)


# ============================================================================
# Legacy stub function (kept for compatibility)
# ============================================================================


def run(stage: str, path: str) -> int:
    """
    Execute a specific pipeline stage.

    Args:
        stage: Pipeline stage (analyze, refactor, validate, export, apply)
        path: Target path to process

    Returns:
        Exit code (0 for success)
    """
    return 0
