"""ACE Kernel - Orchestrates analysis, refactoring, and validation."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ace import __version__
from ace.errors import ExitCode
from ace.fileio import read_text_file, write_text_preserving_style
from ace.git_safety import check_git_safety, git_commit_changes, git_stash_changes
from ace.perf import get_profiler
from ace.receipts import Receipt, create_receipt
from ace.safety import content_hash, is_idempotent
from ace.skills.config import analyze_yaml_duplicate_keys
from ace.skills.markdown import analyze_markdown_dangerous_commands
from ace.skills.python import (
    EditPlan,
    analyze_broad_except,
    analyze_import_sort,
    analyze_py,
    analyze_subprocess_check,
    analyze_subprocess_shell,
    analyze_subprocess_string_cmd,
    refactor_broad_except,
    refactor_import_sort,
    refactor_py_timeout,
    refactor_subprocess_check,
    validate_python_syntax,
)
from ace.skills.shell import analyze_shell_strict_mode
from ace.storage import AnalysisCache, compute_file_hash, compute_ruleset_hash
from ace.suppressions import filter_findings_by_suppressions, parse_suppressions
from ace.uir import UnifiedIssue


def run_analyze(
    target_path: Path | str,
    rules: list[str] | None = None,
    use_cache: bool = True,
    cache_ttl: int = 3600,
    cache_dir: str = ".ace",
    jobs: int = 1,
) -> list[UnifiedIssue]:
    """
    Run analysis on target path and collect findings.

    Args:
        target_path: Directory or file to analyze (Path or str)
        rules: Optional list of rule IDs to run (None = all rules)
        use_cache: Whether to use analysis cache (default: True)
        cache_ttl: Cache TTL in seconds (default: 3600)
        cache_dir: Cache directory (default: .ace)
        jobs: Number of parallel workers (default: 1 for sequential)

    Returns:
        List of UnifiedIssue findings (sorted deterministically)
    """
    profiler = get_profiler()
    profiler.start_phase("analyze")

    # Convert str to Path if needed
    if isinstance(target_path, str):
        target_path = Path(target_path)

    # Normalize rules filter
    rules_filter = {r.upper() for r in rules} if rules else None

    # Initialize cache if enabled
    cache = AnalysisCache(cache_dir=cache_dir, ttl=cache_ttl) if use_cache else None

    # Compute ruleset hash for cache key
    all_rule_ids = [
        "PY-S101-UNSAFE-HTTP",
        "PY-E201-BROAD-EXCEPT",
        "PY-I101-IMPORT-SORT",
        "PY-S201-SUBPROCESS-CHECK",
        "PY-S202-SUBPROCESS-SHELL",
        "PY-S203-SUBPROCESS-STRING-CMD",
        "MD-S001-DANGEROUS-COMMAND",
        "YML-F001-DUPLICATE-KEY",
        "SH-S001-MISSING-STRICT-MODE",
    ]
    enabled_rules = [r for r in all_rule_ids if should_run_rule_static(r, rules_filter)]
    ruleset_hash = compute_ruleset_hash(enabled_rules, __version__)

    def should_run_rule(rule_id: str) -> bool:
        """Check if rule should be run based on filter."""
        return should_run_rule_static(rule_id, rules_filter)

    # Helper function to analyze a single file
    def analyze_file(file_path: Path, file_index: int) -> tuple[int, list[UnifiedIssue]]:
        """Analyze a single file and return (index, findings) for deterministic sorting."""
        try:
            # Use robust file I/O with encoding/newline handling
            content, _ = read_text_file(file_path, preserve_newlines=False)
            path_str = str(file_path)

            # Compute file hash for cache key
            file_hash = compute_file_hash(content)

            # Try cache first
            if cache:
                cached_findings = cache.get(path_str, file_hash, ruleset_hash)
                if cached_findings is not None:
                    # Cache hit: restore UnifiedIssue objects from dicts
                    findings = [_dict_to_uir(finding_dict) for finding_dict in cached_findings]
                    return (file_index, findings)

            # Cache miss: perform analysis
            # Parse suppressions for this file
            suppressions = parse_suppressions(content)

            # Collect findings for this file
            file_findings = []

            # Python rules
            if file_path.suffix == ".py":
                if should_run_rule("PY-S101-UNSAFE-HTTP"):
                    file_findings.extend(analyze_py(content, path_str))
                if should_run_rule("PY-E201-BROAD-EXCEPT"):
                    file_findings.extend(analyze_broad_except(content, path_str))
                if should_run_rule("PY-I101-IMPORT-SORT"):
                    file_findings.extend(analyze_import_sort(content, path_str))
                if should_run_rule("PY-S201-SUBPROCESS-CHECK"):
                    file_findings.extend(analyze_subprocess_check(content, path_str))
                if should_run_rule("PY-S202-SUBPROCESS-SHELL"):
                    file_findings.extend(analyze_subprocess_shell(content, path_str))
                if should_run_rule("PY-S203-SUBPROCESS-STRING-CMD"):
                    file_findings.extend(analyze_subprocess_string_cmd(content, path_str))

            # Markdown rules
            elif file_path.suffix == ".md":
                if should_run_rule("MD-S001-DANGEROUS-COMMAND"):
                    file_findings.extend(
                        analyze_markdown_dangerous_commands(content, path_str)
                    )

            # YAML rules
            elif file_path.suffix in {".yml", ".yaml"}:
                if should_run_rule("YML-F001-DUPLICATE-KEY"):
                    file_findings.extend(analyze_yaml_duplicate_keys(content, path_str))

            # Shell rules
            elif file_path.suffix == ".sh" or (
                file_path.suffix == "" and content.startswith("#!")
            ):
                if should_run_rule("SH-S001-MISSING-STRICT-MODE"):
                    file_findings.extend(analyze_shell_strict_mode(content, path_str))

            # Filter out suppressed findings
            file_findings = filter_findings_by_suppressions(file_findings, suppressions)

            # Store in cache (as dicts for deterministic serialization)
            if cache and file_findings:
                cache.set(
                    path_str,
                    file_hash,
                    ruleset_hash,
                    [f.to_dict() for f in file_findings],
                )

            return (file_index, file_findings)

        except Exception:
            # Skip files that can't be read or analyzed
            return (file_index, [])

    # Collect files to analyze
    if target_path.is_file():
        files = [target_path]
    else:
        # Collect all files (sorted for determinism)
        files = sorted(target_path.rglob("*"))
        files = [f for f in files if f.is_file()]

    # Analyze files (parallel or sequential)
    indexed_results: list[tuple[int, list[UnifiedIssue]]] = []

    if jobs > 1:
        # Parallel execution with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = {
                executor.submit(analyze_file, file_path, idx): idx
                for idx, file_path in enumerate(files)
            }

            for future in as_completed(futures):
                file_index, findings = future.result()
                if findings:
                    indexed_results.append((file_index, findings))
    else:
        # Sequential execution
        for idx, file_path in enumerate(files):
            file_index, findings = analyze_file(file_path, idx)
            if findings:
                indexed_results.append((file_index, findings))

    # Sort by original file index for determinism, then extract findings
    indexed_results.sort(key=lambda x: x[0])
    all_findings = []
    for _, findings in indexed_results:
        all_findings.extend(findings)

    # Final sort by (file, line, rule) for complete determinism
    all_findings.sort(key=lambda f: (f.file, f.line, f.rule))

    profiler.stop_phase("analyze")
    return all_findings


def should_run_rule_static(rule_id: str, rules_filter: set[str] | None) -> bool:
    """Check if rule should be run based on filter (static helper)."""
    if rules_filter is None:
        return True
    return rule_id.upper() in rules_filter


def _dict_to_uir(finding_dict: dict) -> UnifiedIssue:
    """Convert finding dict back to UnifiedIssue."""
    from ace.uir import Severity

    return UnifiedIssue(
        file=finding_dict["file"],
        line=finding_dict["line"],
        rule=finding_dict["rule"],
        severity=Severity(finding_dict["severity"]),
        message=finding_dict["message"],
        suggestion=finding_dict.get("suggestion", ""),
        snippet=finding_dict.get("snippet", ""),
    )


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
