"""Tests for ACE parallel execution."""

import json
import tempfile
from pathlib import Path

from ace.kernel import run_analyze


def test_sequential_vs_parallel_identical():
    """Test that sequential and parallel execution produce identical outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple test files with issues
        for i in range(10):
            test_file = Path(tmpdir) / f"test{i}.py"
            test_file.write_text(
                f"""import os
import sys

def func_{i}():
    pass
""",
                encoding="utf-8",
            )

        # Run sequential analysis
        findings_seq = run_analyze(tmpdir, jobs=1, use_cache=False)
        output_seq = json.dumps(
            [f.to_dict() for f in findings_seq], sort_keys=True, indent=2
        )

        # Run parallel analysis
        findings_par = run_analyze(tmpdir, jobs=4, use_cache=False)
        output_par = json.dumps(
            [f.to_dict() for f in findings_par], sort_keys=True, indent=2
        )

        # Outputs should be byte-identical
        assert output_seq == output_par


def test_parallel_multiple_runs_deterministic():
    """Test that parallel execution is deterministic across multiple runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        for i in range(5):
            test_file = Path(tmpdir) / f"test{i}.py"
            test_file.write_text(
                f"""import os

def func_{i}():
    pass
""",
                encoding="utf-8",
            )

        # Run parallel analysis twice
        findings1 = run_analyze(tmpdir, jobs=2, use_cache=False)
        output1 = json.dumps([f.to_dict() for f in findings1], sort_keys=True)

        findings2 = run_analyze(tmpdir, jobs=2, use_cache=False)
        output2 = json.dumps([f.to_dict() for f in findings2], sort_keys=True)

        # Outputs should be identical
        assert output1 == output2


def test_parallel_with_cache():
    """Test that parallel execution works correctly with caching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        for i in range(8):
            test_file = Path(tmpdir) / f"test{i}.py"
            test_file.write_text(
                f"""import os
import sys

def func_{i}():
    pass
""",
                encoding="utf-8",
            )

        cache_dir = Path(tmpdir) / "cache"

        # First run (cold cache, parallel)
        findings_cold = run_analyze(tmpdir, jobs=4, use_cache=True, cache_dir=str(cache_dir))
        output_cold = json.dumps([f.to_dict() for f in findings_cold], sort_keys=True)

        # Second run (warm cache, parallel)
        findings_warm = run_analyze(tmpdir, jobs=4, use_cache=True, cache_dir=str(cache_dir))
        output_warm = json.dumps([f.to_dict() for f in findings_warm], sort_keys=True)

        # Outputs should be identical
        assert output_cold == output_warm


def test_parallel_jobs_1_equals_sequential():
    """Test that --jobs 1 is equivalent to sequential execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("import os\nimport sys\n", encoding="utf-8")

        # Sequential (no jobs parameter, defaults to 1)
        findings_seq = run_analyze(tmpdir, use_cache=False)
        output_seq = json.dumps([f.to_dict() for f in findings_seq], sort_keys=True)

        # Parallel with jobs=1
        findings_par1 = run_analyze(tmpdir, jobs=1, use_cache=False)
        output_par1 = json.dumps([f.to_dict() for f in findings_par1], sort_keys=True)

        # Should be identical
        assert output_seq == output_par1


def test_parallel_finding_order_deterministic():
    """Test that parallel execution maintains deterministic finding order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files with predictable issues
        files = []
        for i in range(15):
            test_file = Path(tmpdir) / f"file_{i:02d}.py"
            test_file.write_text(
                f"""# File {i}
import os
import sys

def function_{i}():
    pass
""",
                encoding="utf-8",
            )
            files.append(test_file)

        # Run parallel analysis multiple times
        outputs = []
        for _ in range(3):
            findings = run_analyze(tmpdir, jobs=4, use_cache=False)
            # Extract just file and rule for comparison
            output = [(f.file, f.rule, f.line) for f in findings]
            outputs.append(output)

        # All runs should have identical ordering
        assert outputs[0] == outputs[1] == outputs[2]


def test_parallel_empty_directory():
    """Test parallel execution on empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run on empty directory
        findings_seq = run_analyze(tmpdir, jobs=1, use_cache=False)
        findings_par = run_analyze(tmpdir, jobs=4, use_cache=False)

        # Both should return empty
        assert len(findings_seq) == 0
        assert len(findings_par) == 0


def test_parallel_single_file():
    """Test parallel execution on single file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "single.py"
        test_file.write_text("import os\n", encoding="utf-8")

        # Sequential
        findings_seq = run_analyze(test_file, jobs=1, use_cache=False)
        output_seq = json.dumps([f.to_dict() for f in findings_seq], sort_keys=True)

        # Parallel
        findings_par = run_analyze(test_file, jobs=4, use_cache=False)
        output_par = json.dumps([f.to_dict() for f in findings_par], sort_keys=True)

        # Should be identical
        assert output_seq == output_par


def test_parallel_various_file_types():
    """Test parallel execution across different file types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Python file
        (Path(tmpdir) / "test.py").write_text("import os\n", encoding="utf-8")

        # Markdown file
        (Path(tmpdir) / "test.md").write_text("```bash\nrm -rf /\n```\n", encoding="utf-8")

        # YAML file
        (Path(tmpdir) / "test.yml").write_text("key: value\nkey: duplicate\n", encoding="utf-8")

        # Shell file
        (Path(tmpdir) / "test.sh").write_text("#!/bin/bash\necho test\n", encoding="utf-8")

        # Sequential
        findings_seq = run_analyze(tmpdir, jobs=1, use_cache=False)
        output_seq = json.dumps([f.to_dict() for f in findings_seq], sort_keys=True)

        # Parallel
        findings_par = run_analyze(tmpdir, jobs=3, use_cache=False)
        output_par = json.dumps([f.to_dict() for f in findings_par], sort_keys=True)

        # Should be identical
        assert output_seq == output_par
