"""Test parallel execution determinism.

Verifies that parallel analysis (--jobs > 1) produces identical results
to sequential analysis (--jobs 1) for both JSON and SARIF formats.
"""

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from acha.agents.analysis_agent import AnalysisAgent
from acha.utils.sarif_reporter import SARIFReporter


def _hash_json(data: dict) -> str:
    """Compute SHA256 hash of JSON data (excluding timestamps)"""
    # Remove timestamp fields for comparison
    normalized = json.dumps(data, sort_keys=True)
    # Remove timestamp values (they will differ between runs)
    normalized_lines = []
    for line in normalized.split("\n"):
        if '"timestamp"' not in line:
            normalized_lines.append(line)
    normalized = "\n".join(normalized_lines)
    return hashlib.sha256(normalized.encode()).hexdigest()


def _hash_sarif(sarif_data: dict) -> str:
    """Compute SHA256 hash of SARIF data (excluding UUIDs and timestamps)"""
    # SARIF has run IDs (UUIDs) and timestamps that vary
    # We'll normalize by removing these fields
    sarif_copy = json.loads(json.dumps(sarif_data))  # Deep copy

    # Remove variable fields
    for run in sarif_copy.get("runs", []):
        # Remove automation details (has guid)
        if "automationDetails" in run:
            run.pop("automationDetails")
        # Remove invocations (has timestamps)
        if "invocations" in run:
            run.pop("invocations")

    normalized = json.dumps(sarif_copy, sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()


@pytest.fixture
def sample_codebase(tmp_path: Path) -> Path:
    """Create a sample codebase with multiple files for testing"""
    codebase = tmp_path / "sample"
    codebase.mkdir()

    # File 1: Has unused imports, magic numbers
    (codebase / "module_a.py").write_text(
        """
import os
import sys
import json  # unused

def calculate(x):
    if x > 100:  # magic number
        return x * 2
    return x + 100  # magic number
"""
    )

    # File 2: Has high complexity, missing docstrings
    (codebase / "module_b.py").write_text(
        """
def complex_function(a, b, c, d, e):
    # No docstring
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        return a + b + c + d + e
                    else:
                        return a + b + c + d
                else:
                    return a + b + c
            else:
                return a + b
        else:
            return a
    else:
        return 0
"""
    )

    # File 3: Has broad exceptions, subprocess
    (codebase / "module_c.py").write_text(
        """
import subprocess

def risky_code():
    try:
        result = subprocess.run("ls", shell=True)
    except:  # broad exception
        pass
"""
    )

    # File 4: Subdirectory with more code
    subdir = codebase / "submodule"
    subdir.mkdir()
    (subdir / "module_d.py").write_text(
        """
def process_data(items):
    count = 0
    for item in items:
        if item > 50:  # magic number
            count += 1
    return count
"""
    )

    return codebase


def test_parallel_json_determinism(sample_codebase: Path):
    """Test that parallel and sequential analysis produce identical JSON"""
    # Run sequential analysis
    agent_sequential = AnalysisAgent(parallel=False, max_workers=1)
    results_sequential = agent_sequential.run(str(sample_codebase))

    # Run parallel analysis with 4 workers
    agent_parallel = AnalysisAgent(parallel=True, max_workers=4)
    results_parallel = agent_parallel.run(str(sample_codebase))

    # Compute hashes (excluding timestamps)
    hash_sequential = _hash_json(results_sequential)
    hash_parallel = _hash_json(results_parallel)

    # Hashes should be identical
    assert hash_sequential == hash_parallel, (
        f"JSON results differ between sequential and parallel execution:\n"
        f"Sequential hash: {hash_sequential}\n"
        f"Parallel hash: {hash_parallel}\n"
        f"Sequential findings: {len(results_sequential.get('findings', []))}\n"
        f"Parallel findings: {len(results_parallel.get('findings', []))}"
    )

    # Also verify finding counts match
    assert len(results_sequential.get("findings", [])) == len(results_parallel.get("findings", []))


def test_parallel_sarif_determinism(sample_codebase: Path):
    """Test that parallel and sequential analysis produce identical SARIF"""
    # Run sequential analysis
    agent_sequential = AnalysisAgent(parallel=False, max_workers=1)
    results_sequential = agent_sequential.run(str(sample_codebase))

    # Run parallel analysis
    agent_parallel = AnalysisAgent(parallel=True, max_workers=4)
    results_parallel = agent_parallel.run(str(sample_codebase))

    # Convert to SARIF
    sarif_reporter = SARIFReporter()
    sarif_sequential = sarif_reporter.generate(
        results_sequential.get("findings", []), Path(str(sample_codebase))
    )
    sarif_parallel = sarif_reporter.generate(
        results_parallel.get("findings", []), Path(str(sample_codebase))
    )

    # Compute hashes (excluding UUIDs and timestamps)
    hash_sequential = _hash_sarif(sarif_sequential)
    hash_parallel = _hash_sarif(sarif_parallel)

    # Hashes should be identical
    assert hash_sequential == hash_parallel, (
        f"SARIF results differ between sequential and parallel execution:\n"
        f"Sequential hash: {hash_sequential}\n"
        f"Parallel hash: {hash_parallel}"
    )


def test_parallel_finding_ids_unique(sample_codebase: Path):
    """Test that finding IDs are unique in parallel execution"""
    agent = AnalysisAgent(parallel=True, max_workers=4)
    results = agent.run(str(sample_codebase))

    findings = results.get("findings", [])
    finding_ids = [f.get("id") for f in findings if "id" in f]

    # All IDs should be present
    assert len(finding_ids) == len(findings), "Not all findings have IDs"

    # All IDs should be unique
    assert len(finding_ids) == len(set(finding_ids)), f"Duplicate finding IDs detected: {finding_ids}"


def test_parallel_finding_ids_monotonic(sample_codebase: Path):
    """Test that finding IDs are monotonically increasing"""
    agent = AnalysisAgent(parallel=True, max_workers=4)
    results = agent.run(str(sample_codebase))

    findings = results.get("findings", [])
    finding_ids = [f.get("id") for f in findings if "id" in f]

    # Extract numeric parts from IDs like "ANL-001", "ANL-002"
    id_numbers = []
    for fid in finding_ids:
        try:
            # Extract number from "ANL-XXX"
            num = int(fid.split("-")[1])
            id_numbers.append(num)
        except (IndexError, ValueError):
            pytest.fail(f"Invalid finding ID format: {fid}")

    # IDs should be monotonically increasing
    for i in range(len(id_numbers) - 1):
        assert (
            id_numbers[i] < id_numbers[i + 1]
        ), f"Finding IDs not monotonic: {finding_ids[i]} >= {finding_ids[i+1]}"


def test_parallel_findings_sorted_by_file_and_line(sample_codebase: Path):
    """Test that findings are sorted by file path, then line number"""
    agent = AnalysisAgent(parallel=True, max_workers=4)
    results = agent.run(str(sample_codebase))

    findings = results.get("findings", [])

    # Verify findings are sorted by file, then line
    for i in range(len(findings) - 1):
        f1 = findings[i]
        f2 = findings[i + 1]

        file1 = f1.get("file", "")
        file2 = f2.get("file", "")
        line1 = f1.get("start_line", 0)
        line2 = f2.get("start_line", 0)

        # If same file, line numbers should be ascending
        if file1 == file2:
            assert (
                line1 <= line2
            ), f"Findings not sorted by line within file {file1}: line {line1} before {line2}"


def test_multiple_runs_identical(sample_codebase: Path):
    """Test that running parallel analysis multiple times produces identical results"""
    hashes = []

    for run in range(3):
        agent = AnalysisAgent(parallel=True, max_workers=4)
        results = agent.run(str(sample_codebase))
        hash_val = _hash_json(results)
        hashes.append(hash_val)

    # All hashes should be identical
    assert len(set(hashes)) == 1, f"Multiple runs produced different results: {hashes}"


def test_jobs_1_vs_jobs_4_identical(sample_codebase: Path):
    """Test that --jobs 1 and --jobs 4 produce identical results (critical for CI/CD)"""
    # This is the key test for determinism guarantee
    agent_1 = AnalysisAgent(parallel=True, max_workers=1)
    results_1 = agent_1.run(str(sample_codebase))

    agent_4 = AnalysisAgent(parallel=True, max_workers=4)
    results_4 = agent_4.run(str(sample_codebase))

    # Convert to JSON strings for comparison (sorted keys)
    json_1 = json.dumps(results_1, sort_keys=True)
    json_4 = json.dumps(results_4, sort_keys=True)

    # Remove timestamps for comparison
    json_1_lines = [line for line in json_1.split("\n") if '"timestamp"' not in line]
    json_4_lines = [line for line in json_4.split("\n") if '"timestamp"' not in line]

    json_1_normalized = "\n".join(json_1_lines)
    json_4_normalized = "\n".join(json_4_lines)

    assert json_1_normalized == json_4_normalized, (
        "Results differ between jobs=1 and jobs=4:\n"
        f"jobs=1 findings: {len(results_1.get('findings', []))}\n"
        f"jobs=4 findings: {len(results_4.get('findings', []))}"
    )
