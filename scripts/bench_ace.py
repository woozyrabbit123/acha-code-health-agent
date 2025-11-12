#!/usr/bin/env python3
"""Benchmark script for ACE performance testing.

Exercises ACE analysis with sequential and parallel execution to measure
performance impact and verify determinism.

Usage:
    python scripts/bench_ace.py [--target PATH] [--max-jobs N]
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def create_sample_files(base_dir: Path, count: int = 20):
    """
    Create sample Python files for benchmarking.

    Args:
        base_dir: Directory to create files in
        count: Number of files to create
    """
    for i in range(count):
        file_path = base_dir / f"sample_{i:03d}.py"
        file_path.write_text(
            f"""# Sample file {i}
import os
import sys

def function_{i}():
    '''Sample function {i}.'''
    try:
        result = os.environ.get('VAR_{i}')
        return result
    except:
        pass

class Class{i}:
    '''Sample class {i}.'''
    def method(self):
        pass
""",
            encoding="utf-8",
        )


def run_analysis(target: Path, jobs: int = 1, profile: Path | None = None) -> tuple[float, str]:
    """
    Run ACE analysis and measure execution time.

    Args:
        target: Target directory to analyze
        jobs: Number of parallel workers
        profile: Optional path to save performance profile

    Returns:
        Tuple of (duration_seconds, output_json)
    """
    cmd = [sys.executable, "-m", "ace.cli", "analyze", "--target", str(target), "--jobs", str(jobs)]

    if profile:
        cmd.extend(["--profile", str(profile)])

    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    duration = time.perf_counter() - start

    if result.returncode != 0:
        print(f"ERROR: Analysis failed (jobs={jobs})", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    return duration, result.stdout


def main():
    """Main benchmark entry point."""
    parser = argparse.ArgumentParser(description="Benchmark ACE analysis performance")
    parser.add_argument(
        "--target", help="Target directory (default: create temporary samples)"
    )
    parser.add_argument(
        "--max-jobs", type=int, default=4, help="Maximum number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--file-count", type=int, default=20, help="Number of sample files to create (default: 20)"
    )

    args = parser.parse_args()

    if args.target:
        target_dir = Path(args.target)
        if not target_dir.exists():
            print(f"ERROR: Target directory does not exist: {target_dir}", file=sys.stderr)
            sys.exit(1)
        cleanup = False
    else:
        # Create temporary sample files
        temp_dir = tempfile.mkdtemp(prefix="ace_bench_")
        target_dir = Path(temp_dir)
        print(f"Creating {args.file_count} sample files in {target_dir}...")
        create_sample_files(target_dir, args.file_count)
        cleanup = True

    try:
        print("\n" + "=" * 70)
        print("ACE Performance Benchmark")
        print("=" * 70)
        print(f"Target: {target_dir}")
        print(f"Files: {len(list(target_dir.glob('*.py')))}")
        print()

        results = {}

        # Benchmark sequential execution
        print("Running sequential analysis (--jobs 1)...")
        duration_seq, output_seq = run_analysis(target_dir, jobs=1)
        results["sequential"] = {"jobs": 1, "duration": duration_seq}
        print(f"  Duration: {duration_seq:.3f}s")

        # Benchmark parallel execution
        for jobs in [2, args.max_jobs]:
            if jobs <= 1:
                continue
            print(f"\nRunning parallel analysis (--jobs {jobs})...")
            duration_par, output_par = run_analysis(target_dir, jobs=jobs)
            results[f"parallel_{jobs}"] = {"jobs": jobs, "duration": duration_par}
            speedup = duration_seq / duration_par if duration_par > 0 else 0
            print(f"  Duration: {duration_par:.3f}s ({speedup:.2f}x speedup)")

            # Verify determinism (outputs should be identical)
            if json.loads(output_seq) != json.loads(output_par):
                print(f"\n⚠️  WARNING: Sequential vs parallel (jobs={jobs}) outputs differ!", file=sys.stderr)
                print("  This violates determinism guarantees!", file=sys.stderr)
            else:
                print(f"  ✓ Output identical to sequential (determinism verified)")

        # Summary
        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)
        for name, data in sorted(results.items()):
            speedup = results["sequential"]["duration"] / data["duration"] if data["duration"] > 0 else 0
            print(f"{name:20s} | jobs={data['jobs']:2d} | {data['duration']:7.3f}s | {speedup:5.2f}x")

        print("=" * 70)
        print("✓ Benchmark complete")

    finally:
        if cleanup:
            import shutil
            shutil.rmtree(target_dir)


if __name__ == "__main__":
    main()
