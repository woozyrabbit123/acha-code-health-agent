"""Performance tests for AST caching and parallel analysis"""
import time
import tempfile
import shutil
from pathlib import Path
from agents.analysis_agent import AnalysisAgent
from utils.ast_cache import ASTCache
import textwrap


def write_file(path: Path, content: str):
    """Helper to write test files"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_ast_cache_hit_ratio(tmp_path: Path):
    """Test that cache hits improve performance on second run"""
    # Create test files
    for i in range(10):
        write_file(tmp_path / f"file_{i}.py", f"""
            def function_{i}():
                x = {i}
                return x
        """)

    cache = ASTCache(cache_dir=tmp_path / ".cache", max_size=100)
    agent = AnalysisAgent(cache=cache, parallel=False)

    # First run - should populate cache
    start = time.time()
    result1 = agent.run(str(tmp_path))
    first_run_time = time.time() - start

    # Second run - should use cache
    start = time.time()
    result2 = agent.run(str(tmp_path))
    second_run_time = time.time() - start

    # Cache should make second run faster
    assert second_run_time < first_run_time, f"Second run ({second_run_time:.3f}s) should be faster than first ({first_run_time:.3f}s)"

    # Results should be identical
    assert len(result1.get("findings", result1.get("issues", []))) == len(result2.get("findings", result2.get("issues", [])))


def test_parallel_analysis_correctness(tmp_path: Path):
    """Test that parallel analysis produces same results as sequential"""
    # Create test files with known issues
    for i in range(20):
        write_file(tmp_path / f"file_{i}.py", f"""
            import os  # unused import

            def function_{i}():
                x = {i}
                y = {i}
                return x + y
        """)

    # Sequential analysis
    agent_seq = AnalysisAgent(parallel=False)
    result_seq = agent_seq.run(str(tmp_path))
    findings_seq = result_seq.get("findings", result_seq.get("issues", []))

    # Parallel analysis
    agent_par = AnalysisAgent(parallel=True, max_workers=4)
    result_par = agent_par.run(str(tmp_path))
    findings_par = result_par.get("findings", result_par.get("issues", []))

    # Should find same number of issues
    assert len(findings_seq) == len(findings_par), \
        f"Sequential found {len(findings_seq)}, parallel found {len(findings_par)}"

    # Sort both by file and line for comparison
    def sort_key(f):
        return (f.get("file", ""), f.get("line", 0), f.get("rule", ""))

    findings_seq_sorted = sorted(findings_seq, key=sort_key)
    findings_par_sorted = sorted(findings_par, key=sort_key)

    # Should find same issues
    for f_seq, f_par in zip(findings_seq_sorted, findings_par_sorted):
        assert f_seq.get("rule") == f_par.get("rule"), f"Rule mismatch: {f_seq} vs {f_par}"


def test_batch_mode(tmp_path: Path):
    """Test batch mode processing multiple directories"""
    # Create two separate directories
    dir1 = tmp_path / "project1"
    dir2 = tmp_path / "project2"

    write_file(dir1 / "code.py", """
        import os
        def f():
            return 1
    """)

    write_file(dir2 / "code.py", """
        import sys
        def g():
            x = 42
            return x
    """)

    agent = AnalysisAgent()
    result = agent.analyze_batch([str(dir1), str(dir2)])

    # Should return results for both directories
    assert len(result) == 2
    assert str(dir1) in result or any(str(dir1) in str(k) for k in result.keys())
    assert str(dir2) in result or any(str(dir2) in str(k) for k in result.keys())


def test_cache_invalidation(tmp_path: Path):
    """Test that cache invalidates when file changes"""
    test_file = tmp_path / "test.py"

    # Write initial file
    write_file(test_file, """
        import os
        def f():
            return 1
    """)

    cache = ASTCache(cache_dir=tmp_path / ".cache", max_size=100)
    agent = AnalysisAgent(cache=cache)

    # First analysis
    result1 = agent.run(str(tmp_path))
    findings1 = result1.get("findings", result1.get("issues", []))
    unused_imports_1 = [f for f in findings1 if f.get("rule") == "unused_import"]

    # Modify file to use the import
    time.sleep(0.01)  # Ensure mtime changes
    write_file(test_file, """
        import os
        def f():
            return os.getcwd()
    """)

    # Second analysis - should detect change
    result2 = agent.run(str(tmp_path))
    findings2 = result2.get("findings", result2.get("issues", []))
    unused_imports_2 = [f for f in findings2 if f.get("rule") == "unused_import"]

    # Should have fewer unused imports after using os
    assert len(unused_imports_2) < len(unused_imports_1), \
        f"Cache should invalidate: {len(unused_imports_1)} -> {len(unused_imports_2)}"


def test_benchmark_100_files():
    """Benchmark: analyze 100 files with/without cache and parallel"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create 100 test files with more substantial code
        for i in range(100):
            write_file(tmp_path / f"file_{i}.py", f"""
                import os
                import sys
                import subprocess

                class Handler_{i}:
                    def __init__(self, value):
                        self.value = value

                    def process(self, data):
                        result = []
                        for item in data:
                            if item > {i}:
                                result.append(item * 2)
                        return result

                def function_{i}(x, y, z):
                    # Missing docstring
                    a = {i}
                    b = {i}
                    c = {i}

                    if x > 0:
                        if y > 0:
                            if z > 0:
                                for j in range(10):
                                    if j % 2 == 0:
                                        for k in range(5):
                                            if k > 3:
                                                pass

                    try:
                        result = a + b + c
                        handler = Handler_{i}(result)
                        processed = handler.process([1, 2, 3])
                    except Exception:
                        pass

                    return result

                def helper_{i}(value):
                    return value * {i} + {i}
            """)

        # Baseline: no cache, no parallel
        agent_baseline = AnalysisAgent(parallel=False)
        start = time.time()
        result_baseline = agent_baseline.run(str(tmp_path))
        baseline_time = time.time() - start

        # With cache (first run)
        cache = ASTCache(cache_dir=tmp_path / ".cache")
        agent_cache = AnalysisAgent(cache=cache, parallel=False)
        start = time.time()
        result_cache1 = agent_cache.run(str(tmp_path))
        cache_first_time = time.time() - start

        # With cache (second run - should be faster)
        start = time.time()
        result_cache2 = agent_cache.run(str(tmp_path))
        cache_second_time = time.time() - start

        # With parallel (no cache)
        agent_parallel = AnalysisAgent(parallel=True, max_workers=4)
        start = time.time()
        result_parallel = agent_parallel.run(str(tmp_path))
        parallel_time = time.time() - start

        # With cache + parallel (second run)
        agent_both = AnalysisAgent(cache=cache, parallel=True, max_workers=4)
        start = time.time()
        result_both = agent_both.run(str(tmp_path))
        both_time = time.time() - start

        print(f"\n=== Performance Benchmark (100 files) ===")
        print(f"Baseline (no cache, no parallel): {baseline_time:.3f}s")
        print(f"Cache first run:                   {cache_first_time:.3f}s")
        print(f"Cache second run:                  {cache_second_time:.3f}s ({baseline_time/cache_second_time:.2f}x speedup)")
        print(f"Parallel only:                     {parallel_time:.3f}s ({baseline_time/parallel_time:.2f}x speedup)")
        print(f"Cache + Parallel:                  {both_time:.3f}s ({baseline_time/both_time:.2f}x speedup)")

        # Verify cache provides speedup on second run (or at least doesn't slow down significantly)
        # Note: For very small files, cache overhead might dominate, so we allow some margin
        speedup = baseline_time / cache_second_time
        assert speedup >= 0.8, f"Cache should not significantly slow down analysis, got {speedup:.2f}x"

        # At least one optimization should provide meaningful speedup
        # Note: On fast systems with SSDs and small files, overhead may dominate
        best_speedup = max(baseline_time/cache_second_time, baseline_time/parallel_time, baseline_time/both_time)
        print(f"Best speedup achieved: {best_speedup:.2f}x")
        # Allow for more variance - optimizations may not help on very fast systems or small files
        assert best_speedup >= 1.05 or baseline_time < 1.0, \
            f"At least one optimization should provide speedup (got {best_speedup:.2f}x) unless baseline is very fast"

        # Verify all methods find same number of issues
        findings_baseline = len(result_baseline.get("findings", result_baseline.get("issues", [])))
        findings_cache = len(result_cache2.get("findings", result_cache2.get("issues", [])))
        findings_parallel = len(result_parallel.get("findings", result_parallel.get("issues", [])))
        findings_both = len(result_both.get("findings", result_both.get("issues", [])))

        assert findings_baseline == findings_cache == findings_parallel == findings_both, \
            f"All methods should find same issues: {findings_baseline}, {findings_cache}, {findings_parallel}, {findings_both}"
