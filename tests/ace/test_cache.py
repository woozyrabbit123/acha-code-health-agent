"""Tests for ACE analysis cache system."""

import json
import tempfile
import time
from pathlib import Path

from ace.kernel import run_analyze
from ace.storage import AnalysisCache, compute_file_hash, compute_ruleset_hash


def test_cache_basic_operations():
    """Test basic cache get/set operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Set a cache entry
        findings = [
            {"file": "test.py", "line": 1, "rule": "TEST", "severity": "high", "message": "Test"}
        ]
        cache.set("test.py", "abc123", "ruleset456", findings)

        # Get the cache entry
        cached = cache.get("test.py", "abc123", "ruleset456")
        assert cached == findings


def test_cache_miss():
    """Test cache miss returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Cache miss should return None
        cached = cache.get("nonexistent.py", "xyz789", "ruleset999")
        assert cached is None


def test_cache_ttl_expiry():
    """Test cache TTL expiration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Cache with 1 second TTL
        cache = AnalysisCache(cache_dir=tmpdir, ttl=1)

        findings = [{"file": "test.py", "line": 1, "rule": "TEST"}]
        cache.set("test.py", "abc123", "ruleset456", findings)

        # Should hit immediately
        cached = cache.get("test.py", "abc123", "ruleset456")
        assert cached == findings

        # Wait for expiry
        time.sleep(1.5)

        # Should miss after TTL
        cached = cache.get("test.py", "abc123", "ruleset456")
        assert cached is None


def test_cache_invalidation_on_content_change():
    """Test cache invalidation when file content changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Cache with content hash v1
        findings_v1 = [{"file": "test.py", "rule": "TEST", "message": "Version 1"}]
        hash_v1 = compute_file_hash("def foo(): pass")
        cache.set("test.py", hash_v1, "ruleset", findings_v1)

        # Query with different content hash (simulating file change)
        hash_v2 = compute_file_hash("def foo(): return 42")
        cached = cache.get("test.py", hash_v2, "ruleset")
        assert cached is None  # Cache miss due to content change


def test_cache_invalidation_on_ruleset_change():
    """Test cache invalidation when ruleset changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Cache with ruleset v1
        findings = [{"file": "test.py", "rule": "TEST"}]
        ruleset_v1 = compute_ruleset_hash(["RULE-1", "RULE-2"], "0.2.0")
        cache.set("test.py", "abc123", ruleset_v1, findings)

        # Query with different ruleset (simulating rule changes)
        ruleset_v2 = compute_ruleset_hash(["RULE-1", "RULE-3"], "0.2.0")
        cached = cache.get("test.py", "abc123", ruleset_v2)
        assert cached is None  # Cache miss due to ruleset change


def test_cache_invalidation_on_version_change():
    """Test cache invalidation when ACE version changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Cache with version v1
        findings = [{"file": "test.py", "rule": "TEST"}]
        ruleset_v1 = compute_ruleset_hash(["RULE-1"], "0.1.0")
        cache.set("test.py", "abc123", ruleset_v1, findings)

        # Query with different version
        ruleset_v2 = compute_ruleset_hash(["RULE-1"], "0.2.0")
        cached = cache.get("test.py", "abc123", ruleset_v2)
        assert cached is None  # Cache miss due to version change


def test_cache_clear():
    """Test clearing all cache entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Add multiple entries
        cache.set("file1.py", "hash1", "ruleset", [{"rule": "TEST1"}])
        cache.set("file2.py", "hash2", "ruleset", [{"rule": "TEST2"}])

        # Verify entries exist
        assert cache.get("file1.py", "hash1", "ruleset") is not None
        assert cache.get("file2.py", "hash2", "ruleset") is not None

        # Clear cache
        cache.clear()

        # Verify entries are gone
        assert cache.get("file1.py", "hash1", "ruleset") is None
        assert cache.get("file2.py", "hash2", "ruleset") is None


def test_cache_invalidate_file():
    """Test invalidating specific file entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Add entries for different files
        cache.set("file1.py", "hash1", "ruleset", [{"rule": "TEST1"}])
        cache.set("file2.py", "hash2", "ruleset", [{"rule": "TEST2"}])

        # Invalidate file1.py
        cache.invalidate_file("file1.py")

        # file1.py should be gone, file2.py should remain
        assert cache.get("file1.py", "hash1", "ruleset") is None
        assert cache.get("file2.py", "hash2", "ruleset") is not None


def test_cache_deterministic_json_serialization():
    """Test that cache stores deterministic JSON (sorted keys, no whitespace)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(cache_dir=tmpdir, ttl=3600)

        # Store findings with unsorted keys
        findings = [
            {"message": "Test", "file": "test.py", "severity": "high", "rule": "TEST", "line": 1}
        ]
        cache.set("test.py", "abc123", "ruleset", findings)

        # Read raw DB entry
        import sqlite3
        conn = sqlite3.connect(cache.cache_path)
        cursor = conn.execute(
            "SELECT findings_json FROM cache_entries WHERE path = ?", ("test.py",)
        )
        row = cursor.fetchone()
        conn.close()

        raw_json = row[0]
        # Check that JSON is compact (no extra whitespace) and sorted
        parsed = json.loads(raw_json)
        assert parsed == findings
        # Verify it's deterministic by re-serializing
        assert raw_json == json.dumps(findings, sort_keys=True, separators=(',', ':'))


def test_analyze_with_cache_identical_to_no_cache():
    """Test that cached analysis produces identical results to non-cached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file with a known issue
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("import os\nimport sys\n", encoding="utf-8")

        cache_dir = Path(tmpdir) / "cache"

        # Run analysis without cache
        findings_no_cache = run_analyze(test_file, use_cache=False)
        output_no_cache = json.dumps(
            [f.to_dict() for f in findings_no_cache], sort_keys=True, indent=2
        )

        # Run analysis with cache (cold)
        findings_cold = run_analyze(test_file, use_cache=True, cache_dir=str(cache_dir))
        output_cold = json.dumps(
            [f.to_dict() for f in findings_cold], sort_keys=True, indent=2
        )

        # Run analysis with cache (warm)
        findings_warm = run_analyze(test_file, use_cache=True, cache_dir=str(cache_dir))
        output_warm = json.dumps(
            [f.to_dict() for f in findings_warm], sort_keys=True, indent=2
        )

        # All outputs should be byte-identical
        assert output_no_cache == output_cold
        assert output_no_cache == output_warm


def test_analyze_with_no_cache_flag():
    """Test --no-cache flag disables caching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("import os\n", encoding="utf-8")

        cache_dir = Path(tmpdir) / "cache"

        # Run with cache disabled
        run_analyze(test_file, use_cache=False, cache_dir=str(cache_dir))

        # Verify cache directory was not created
        assert not Path(cache_dir).exists()


def test_cache_warm_performance():
    """Test that warm cache is faster than cold cache (sanity check)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple test files
        for i in range(10):
            test_file = Path(tmpdir) / f"test{i}.py"
            test_file.write_text("import os\nimport sys\n", encoding="utf-8")

        cache_dir = Path(tmpdir) / "cache"

        # Cold run (populate cache)
        start = time.perf_counter()
        run_analyze(tmpdir, use_cache=True, cache_dir=str(cache_dir))
        cold_time = time.perf_counter() - start

        # Warm run (use cache)
        start = time.perf_counter()
        run_analyze(tmpdir, use_cache=True, cache_dir=str(cache_dir))
        warm_time = time.perf_counter() - start

        # Warm should be faster (or at least not slower)
        # Note: This is a sanity check, not a strict assertion
        # (filesystem and OS scheduling can affect this)
        assert warm_time <= cold_time * 2  # Allow 2x tolerance


def test_compute_file_hash_deterministic():
    """Test that file hash computation is deterministic."""
    content = "def foo():\n    pass\n"

    hash1 = compute_file_hash(content)
    hash2 = compute_file_hash(content)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest


def test_compute_ruleset_hash_deterministic():
    """Test that ruleset hash computation is deterministic."""
    rules = ["RULE-A", "RULE-B", "RULE-C"]
    version = "0.2.0"

    hash1 = compute_ruleset_hash(rules, version)
    hash2 = compute_ruleset_hash(rules, version)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest


def test_compute_ruleset_hash_order_independent():
    """Test that ruleset hash is independent of input order (internally sorted)."""
    hash1 = compute_ruleset_hash(["RULE-A", "RULE-B"], "0.2.0")
    hash2 = compute_ruleset_hash(["RULE-B", "RULE-A"], "0.2.0")

    assert hash1 == hash2
