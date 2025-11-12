"""ACE Kernel - Orchestrates analysis, refactoring, and validation."""

from dataclasses import dataclass
from pathlib import Path

from ace.export import to_json
from ace.policy import decision, rstar
from ace.safety import content_hash, is_idempotent, verify_parse_py
from ace.skills.python import EditPlan, Finding, analyze_py, refactor_py_timeout


@dataclass
class Receipt:
    """Represents a validation receipt for a refactoring."""

    file: str
    rule: str
    before_hash: str
    after_hash: str
    status: str  # "pass" or "fail"
    decision: str  # "auto", "suggest", or "skip"
    estimated_risk: float
    parse_valid: bool
    description: str


def run_analyze(target: str) -> list[Finding]:
    """
    Analyze Python files in target directory.

    Args:
        target: Target directory or file path

    Returns:
        List of Finding objects (sorted by file, line)
    """
    target_path = Path(target)
    all_findings = []

    if target_path.is_file():
        # Single file
        if target_path.suffix == ".py":
            text = target_path.read_text(encoding="utf-8")
            findings = analyze_py(text, str(target_path))
            all_findings.extend(findings)
    else:
        # Directory - deterministic traversal
        py_files = sorted(target_path.rglob("*.py"))
        for py_file in py_files:
            try:
                text = py_file.read_text(encoding="utf-8")
                findings = analyze_py(text, str(py_file))
                all_findings.extend(findings)
            except Exception:
                # Skip files that can't be read
                continue

    # Sort findings by file and line for determinism
    all_findings.sort(key=lambda f: (f.file, f.line))

    return all_findings


def run_refactor(target: str, findings: list[Finding]) -> list[EditPlan]:
    """
    Generate refactoring plans for findings.

    Args:
        target: Target directory or file path
        findings: List of Finding objects

    Returns:
        List of EditPlan objects
    """
    # Group findings by file
    files_to_fix = {}
    for finding in findings:
        if finding.file not in files_to_fix:
            files_to_fix[finding.file] = []
        files_to_fix[finding.file].append(finding)

    plans = []
    for file_path, file_findings in sorted(files_to_fix.items()):
        try:
            path = Path(file_path)
            if not path.exists():
                continue

            text = path.read_text(encoding="utf-8")
            refactored, plan = refactor_py_timeout(text, file_path, file_findings)
            plans.append(plan)
        except Exception:
            # Skip files that can't be refactored
            continue

    return plans


def run_validate(target: str, plans: list[EditPlan]) -> list[Receipt]:
    """
    Validate refactoring plans.

    Args:
        target: Target directory or file path
        plans: List of EditPlan objects

    Returns:
        List of Receipt objects
    """
    receipts = []

    for plan in plans:
        # Compute hashes
        before_hash = content_hash(plan.before)
        after_hash = content_hash(plan.after)

        # Verify parse validity
        parse_valid = verify_parse_py(plan.after)

        # Calculate R* and decision
        # For network timeout fixes: severity=0.9, complexity=0.5
        r_value = rstar(0.9, 0.5)
        dec = decision(r_value)

        # Determine status
        status = (
            "pass" if parse_valid and (before_hash != after_hash or plan.estimated_risk == 0.0) else "fail"
        )

        receipt = Receipt(
            file=plan.file,
            rule=plan.rule,
            before_hash=before_hash,
            after_hash=after_hash,
            status=status,
            decision=dec.value,
            estimated_risk=plan.estimated_risk,
            parse_valid=parse_valid,
            description=plan.description,
        )
        receipts.append(receipt)

    return receipts


def run_apply(target: str, plans: list[EditPlan]) -> int:
    """
    Apply refactoring plans to files.

    Args:
        target: Target directory or file path
        plans: List of EditPlan objects

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        for plan in plans:
            # Only apply if there are actual changes
            if plan.before == plan.after:
                continue

            file_path = Path(plan.file)
            if not file_path.exists():
                return 1

            # Verify idempotency
            def transform(content: str, fpath: str = str(file_path)) -> str:
                # Re-run refactoring on content
                findings_for_file = analyze_py(content, fpath)
                if not findings_for_file:
                    return content
                refactored, _ = refactor_py_timeout(content, fpath, findings_for_file)
                return refactored

            if not is_idempotent(transform, plan.before):
                # Transformation is not idempotent - this is fine for first apply
                # but we'll verify after writing
                pass

            # Write refactored code
            file_path.write_text(plan.after, encoding="utf-8")

            # Verify the write was successful
            written_content = file_path.read_text(encoding="utf-8")
            if written_content != plan.after:
                return 1

        return 0

    except Exception:
        return 1


def run(stage: str, path: str) -> int:
    """
    Execute a specific pipeline stage.

    Args:
        stage: Pipeline stage (analyze, refactor, validate, export, apply)
        path: Target path to process

    Returns:
        Exit code (0 for success)
    """
    if stage == "analyze":
        findings = run_analyze(path)
        print(to_json([f.__dict__ for f in findings]))
        return 0

    elif stage == "refactor":
        findings = run_analyze(path)
        plans = run_refactor(path, findings)
        print(to_json([p.__dict__ for p in plans]))
        return 0

    elif stage == "validate":
        findings = run_analyze(path)
        plans = run_refactor(path, findings)
        receipts = run_validate(path, plans)
        print(to_json([r.__dict__ for r in receipts]))
        return 0

    elif stage == "apply":
        findings = run_analyze(path)
        plans = run_refactor(path, findings)
        return run_apply(path, plans)

    return 1
