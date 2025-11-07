"""Exporter utility for creating proof packs"""
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from jsonschema import validate, ValidationError


def build_proof_pack(
    dist_dir: str = "dist",
    reports_dir: str = "reports",
    patch_path: str = "dist/patch.diff"
) -> str:
    """
    Build a proof pack ZIP containing all evidence artifacts.

    Args:
        dist_dir: Directory for output ZIP
        reports_dir: Directory containing report JSON files
        patch_path: Path to patch diff file

    Returns:
        Absolute path to the created release.zip

    Raises:
        FileNotFoundError: If required JSON files are missing
        ValidationError: If JSON files fail schema validation
    """
    dist_path = Path(dist_dir)
    reports_path = Path(reports_dir)

    # Ensure directories exist
    dist_path.mkdir(exist_ok=True)
    reports_path.mkdir(exist_ok=True)

    # Load and validate required JSON files
    analysis_data = _load_and_validate_json(
        reports_path / "analysis.json",
        Path("schemas/analysis.schema.json")
    )

    patch_summary_data = _load_and_validate_json(
        reports_path / "patch_summary.json",
        Path("schemas/patch_summary.schema.json")
    )

    validate_data = _load_and_validate_json(
        reports_path / "validate.json",
        Path("schemas/validate.schema.json")
    )

    # Generate report.md
    report_md_path = reports_path / "report.md"
    _generate_report_md(
        report_md_path,
        analysis_data,
        patch_summary_data,
        validate_data
    )

    # Create release.zip
    zip_path = dist_path / "release.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add required JSON files
        zf.write(reports_path / "analysis.json", "reports/analysis.json")
        zf.write(reports_path / "patch_summary.json", "reports/patch_summary.json")
        zf.write(reports_path / "validate.json", "reports/validate.json")
        zf.write(report_md_path, "reports/report.md")

        # Add optional files if they exist
        test_output_path = reports_path / "test_output.txt"
        if test_output_path.exists():
            zf.write(test_output_path, "reports/test_output.txt")

        # Add SARIF report if exists
        sarif_path = reports_path / "analysis.sarif"
        if sarif_path.exists():
            zf.write(sarif_path, "reports/analysis.sarif")

        # Add HTML report if exists
        html_path = reports_path / "report.html"
        if html_path.exists():
            zf.write(html_path, "reports/report.html")

        patch_file_path = Path(patch_path)
        if patch_file_path.exists():
            zf.write(patch_file_path, "dist/patch.diff")

    # Return absolute path
    return str(zip_path.resolve())


def _load_and_validate_json(json_path: Path, schema_path: Path) -> Dict[str, Any]:
    """
    Load a JSON file and validate it against a schema.

    Args:
        json_path: Path to JSON file
        schema_path: Path to JSON schema file

    Returns:
        Loaded JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If validation fails
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Required file not found: {json_path}")

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    validate(instance=data, schema=schema)
    return data


def _generate_report_md(
    output_path: Path,
    analysis_data: Dict[str, Any],
    patch_summary_data: Dict[str, Any],
    validate_data: Dict[str, Any]
) -> None:
    """
    Generate a human-readable report.md file.

    Args:
        output_path: Path to write report.md
        analysis_data: Analysis results
        patch_summary_data: Patch summary data
        validate_data: Validation results
    """
    # Extract patch info
    patch_id = patch_summary_data.get('patch_id', 'unknown')
    files_touched = len(patch_summary_data.get('files_touched', []))
    lines_added = patch_summary_data.get('lines_added', 0)
    lines_removed = patch_summary_data.get('lines_removed', 0)

    # Extract analysis info
    findings = analysis_data.get('findings', [])
    total_findings = len(findings)

    # Group findings by type
    finding_counts = {}
    for finding in findings:
        ftype = finding.get('finding', 'unknown')
        finding_counts[ftype] = finding_counts.get(ftype, 0) + 1

    finding_table = "\n".join(
        f"- {ftype}: {count}"
        for ftype, count in sorted(finding_counts.items())
    )
    if not finding_table:
        finding_table = "- No findings"

    # Extract validation info
    status = validate_data.get('status', 'unknown')
    tests_run = validate_data.get('tests_run', 0)
    duration_s = validate_data.get('duration_s', 0)

    # Generate timestamp
    iso_datetime = datetime.utcnow().isoformat() + "Z"

    # Write report
    report_content = f"""# ACHA Code-Health Proof Pack

**Patch ID:** {patch_id}
**Files touched:** {files_touched}
**Diff stats:** +{lines_added} / -{lines_removed}

## Analysis Summary
Findings: {total_findings}
By type:
{finding_table}

## Validation
Status: {status}
Tests run: {tests_run}
Duration: {duration_s}s

## Notes
- Generated by ACHA exporter on {iso_datetime}
- This pack includes machine-readable JSON and a unified diff for audit.
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
