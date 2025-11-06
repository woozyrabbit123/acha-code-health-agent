"""Validation Agent - runs tests and validates changes"""
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any


class ValidationAgent:
    """Agent for validating code changes by running tests"""

    def __init__(self):
        pass

    def run(
        self,
        workdir: str,
        patch_id: str,
        test_cmd: str = "python -m pytest -q --timeout=30"
    ) -> Dict[str, Any]:
        """
        Run tests against the refactored workdir.

        Args:
            workdir: Directory containing code to test
            patch_id: Patch ID to associate with validation
            test_cmd: Test command to run (default: python -m pytest -q --timeout=30)

        Returns:
            Dictionary with validation results
        """
        workdir_path = Path(workdir)
        if not workdir_path.exists():
            raise ValueError(f"Working directory does not exist: {workdir}")

        # Start timer
        start_time = time.time()

        # Run tests
        try:
            result = subprocess.run(
                test_cmd.split(),
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=60  # Overall timeout for the subprocess
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return {
                "patch_id": patch_id,
                "status": "error",
                "duration_s": duration,
                "tests_run": 0,
                "failing_tests": ["Test execution timed out"]
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "patch_id": patch_id,
                "status": "error",
                "duration_s": duration,
                "tests_run": 0,
                "failing_tests": [f"Test execution failed: {str(e)}"]
            }

        # Calculate duration
        duration = time.time() - start_time

        # Save raw output
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        output_file = reports_dir / "test_output.txt"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=== STDOUT ===\n")
            f.write(stdout)
            f.write("\n=== STDERR ===\n")
            f.write(stderr)
            f.write(f"\n=== EXIT CODE: {exit_code} ===\n")

        # Parse pytest output
        tests_run, failing_tests = self._parse_pytest_output(stdout, stderr)

        # Determine status
        if exit_code == 0:
            status = "pass"
        else:
            status = "fail"

        return {
            "patch_id": patch_id,
            "status": status,
            "duration_s": round(duration, 3),
            "tests_run": tests_run,
            "failing_tests": failing_tests
        }

    def _parse_pytest_output(self, stdout: str, stderr: str) -> tuple:
        """
        Parse pytest output to extract test count and failing tests.

        Returns:
            Tuple of (tests_run, failing_tests)
        """
        tests_run = 0
        failing_tests = []

        combined = stdout + "\n" + stderr

        # Look for pytest summary line like "5 passed in 0.16s" or "1 failed, 4 passed"
        # Pattern for passed tests
        passed_match = re.search(r'(\d+)\s+passed', combined)
        if passed_match:
            tests_run += int(passed_match.group(1))

        # Pattern for failed tests
        failed_match = re.search(r'(\d+)\s+failed', combined)
        if failed_match:
            failed_count = int(failed_match.group(1))
            tests_run += failed_count

        # Extract failing test names - look for FAILED pattern
        failed_test_pattern = re.compile(r'FAILED\s+([^\s]+)')
        for match in failed_test_pattern.finditer(combined):
            failing_tests.append(match.group(1))

        # If we have failed tests but no names, create generic entries
        if failed_match and not failing_tests:
            failed_count = int(failed_match.group(1))
            failing_tests = [f"unknown_test_{i+1}" for i in range(failed_count)]

        return tests_run, failing_tests
