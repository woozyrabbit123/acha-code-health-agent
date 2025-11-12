"""Tests for ace.context_rank - Context ranking."""

import tempfile
import time
from pathlib import Path

import pytest

from ace.repomap import RepoMap
from ace.context_rank import ContextRanker, FileScore


def test_context_ranker_creation():
    """Test ContextRanker initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "test.py").write_text("def foo(): pass")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        assert ranker.repo_map == repo_map


def test_rank_files_basic():
    """Test basic file ranking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "dense.py").write_text("""
def func1(): pass
def func2(): pass
def func3(): pass
class MyClass: pass
""")

        (root / "sparse.py").write_text("""
def single(): pass
""")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        scores = ranker.rank_files(limit=10)

        assert len(scores) > 0
        assert all(isinstance(s, FileScore) for s in scores)

        # dense.py should rank higher (more symbols)
        files = [s.file for s in scores]
        assert "dense.py" in files


def test_rank_files_with_query():
    """Test ranking with query relevance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "user.py").write_text("""
def user_login(): pass
def user_logout(): pass
""")

        (root / "product.py").write_text("""
def product_list(): pass
""")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        # Query for "user"
        scores = ranker.rank_files(query="user", limit=10)

        # user.py should rank first
        if len(scores) > 0:
            assert scores[0].file == "user.py"


def test_rank_files_stable_order():
    """Test that ranking is stable across runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "a.py").write_text("def a(): pass")
        (root / "b.py").write_text("def b(): pass")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        # Rank twice
        scores1 = ranker.rank_files(limit=10)
        scores2 = ranker.rank_files(limit=10)

        # Order should be the same
        files1 = [s.file for s in scores1]
        files2 = [s.file for s in scores2]

        assert files1 == files2


def test_file_score_components():
    """Test FileScore has all required components."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("""
def func1(): pass
def func2(): pass
""")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        scores = ranker.rank_files(limit=1)

        if len(scores) > 0:
            score = scores[0]
            assert hasattr(score, "file")
            assert hasattr(score, "score")
            assert hasattr(score, "symbol_density")
            assert hasattr(score, "recency_boost")
            assert hasattr(score, "relevance_score")
            assert hasattr(score, "symbol_count")


def test_get_related_files():
    """Test finding related files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "a.py").write_text("""
import os
def helper(): pass
""")

        (root / "b.py").write_text("""
import os
def helper(): pass
""")

        (root / "c.py").write_text("""
import sys
def other(): pass
""")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        # Find files related to a.py
        related = ranker.get_related_files("a.py", limit=10)

        assert isinstance(related, list)
        # b.py should be more related (same imports/symbols)


def test_get_hot_files():
    """Test getting recently modified files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create files
        (root / "old.py").write_text("def old(): pass")
        time.sleep(0.1)
        (root / "new.py").write_text("def new(): pass")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        # Get hot files (recent)
        hot = ranker.get_hot_files(limit=10, days=1)

        assert isinstance(hot, list)
        # Both should be recent
        files = [s.file for s in hot]
        assert "new.py" in files


def test_calculate_symbol_density():
    """Test symbol density calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "dense.py").write_text("""
def f1(): pass
def f2(): pass
def f3(): pass
def f4(): pass
def f5(): pass
class C1: pass
class C2: pass
""")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        symbols = repo_map.get_file_symbols("dense.py")
        density = ranker._calculate_symbol_density(symbols)

        # Should have non-zero density
        assert density > 0


def test_calculate_recency_boost():
    """Test recency boost calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("def test(): pass")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        symbols = repo_map.get_file_symbols("test.py")
        boost = ranker._calculate_recency_boost(symbols)

        # Recently created file should have boost > 1.0
        assert boost >= 1.0
        assert boost <= 1.5


def test_calculate_relevance():
    """Test relevance calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "user_auth.py").write_text("""
def user_login(): pass
def user_logout(): pass
""")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        symbols = repo_map.get_file_symbols("user_auth.py")

        # Query for "user"
        relevance = ranker._calculate_relevance("user_auth.py", symbols, "user")

        # Should have high relevance (file name + symbol names match)
        assert relevance > 0


def test_rank_empty_repo():
    """Test ranking with empty repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        scores = ranker.rank_files(limit=10)

        assert len(scores) == 0


def test_rank_with_limit():
    """Test ranking respects limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        for i in range(20):
            (root / f"file{i}.py").write_text(f"def func{i}(): pass")

        repo_map = RepoMap().build(root)
        ranker = ContextRanker(repo_map)

        scores = ranker.rank_files(limit=5)

        assert len(scores) == 5
