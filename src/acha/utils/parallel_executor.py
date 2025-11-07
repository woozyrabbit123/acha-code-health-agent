"""Parallel execution utilities for performance"""

import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


class ParallelExecutor:
    """Parallel execution with progress tracking"""

    def __init__(self, max_workers: int = 4, verbose: bool = False):
        """
        Initialize parallel executor.

        Args:
            max_workers: Maximum number of worker threads
            verbose: Print progress information
        """
        self.max_workers = max_workers
        self.verbose = verbose

    def analyze_files(
        self, files: list[Path], analyze_func: Callable[[Path], list[dict]]
    ) -> list[dict]:
        """
        Analyze multiple files in parallel, maintaining order.

        Args:
            files: List of file paths to analyze
            analyze_func: Function to call for each file (should return list of findings)

        Returns:
            Combined list of findings from all files
        """
        if not files:
            return []

        # For single file or very few files, don't use parallelism
        if len(files) == 1:
            return analyze_func(files[0])

        all_findings = []

        if self.verbose:
            print(f"Analyzing {len(files)} files using {self.max_workers} workers...")

        # Use ThreadPoolExecutor for parallel analysis
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all files
            future_to_file = {
                executor.submit(analyze_func, file_path): file_path for file_path in files
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                completed += 1

                try:
                    findings = future.result()
                    if findings:
                        all_findings.extend(findings)

                    if self.verbose and completed % 10 == 0:
                        print(f"  Progress: {completed}/{len(files)} files", file=sys.stderr)

                except Exception as e:
                    if self.verbose:
                        print(f"  Error analyzing {file_path}: {e}", file=sys.stderr)
                    # Continue with other files

        if self.verbose:
            print(f"Completed: {len(files)} files analyzed, {len(all_findings)} findings")

        return all_findings

    def map_parallel(self, func: Callable[[Any], Any], items: list[Any]) -> list[Any]:
        """
        Map a function over items in parallel.

        Args:
            func: Function to apply to each item
            items: List of items to process

        Returns:
            List of results in same order as items
        """
        if not items:
            return []

        if len(items) == 1:
            return [func(items[0])]

        results = [None] * len(items)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all items with their indices
            future_to_index = {executor.submit(func, item): idx for idx, item in enumerate(items)}

            # Collect results maintaining order
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    if self.verbose:
                        print(f"  Error processing item {idx}: {e}", file=sys.stderr)
                    results[idx] = None

        return results
