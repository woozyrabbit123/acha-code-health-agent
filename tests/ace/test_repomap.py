"""Tests for ace.repomap - Symbol indexer."""

import json
import tempfile
from pathlib import Path

import pytest

from ace.repomap import RepoMap, Symbol


def test_symbol_creation():
    """Test Symbol dataclass creation."""
    symbol = Symbol(
        name="test_func",
        type="function",
        file="test.py",
        line=10,
        deps=["os", "sys"],
        mtime=1234567890,
        size=1024
    )

    assert symbol.name == "test_func"
    assert symbol.type == "function"
    assert symbol.file == "test.py"
    assert symbol.line == 10
    assert symbol.deps == ["os", "sys"]


def test_symbol_to_dict():
    """Test Symbol serialization."""
    symbol = Symbol(
        name="MyClass",
        type="class",
        file="module.py",
        line=20,
        deps=["typing"],
        mtime=1234567890,
        size=2048
    )

    d = symbol.to_dict()
    assert d["name"] == "MyClass"
    assert d["type"] == "class"
    assert d["file"] == "module.py"


def test_symbol_from_dict():
    """Test Symbol deserialization."""
    d = {
        "name": "test_func",
        "type": "function",
        "file": "test.py",
        "line": 10,
        "deps": ["os"],
        "mtime": 1234567890,
        "size": 1024
    }

    symbol = Symbol.from_dict(d)
    assert symbol.name == "test_func"
    assert symbol.type == "function"
    assert symbol.line == 10


def test_repomap_build():
    """Test RepoMap.build() on a sample directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create sample Python files
        (root / "module1.py").write_text("""
import os
import sys

def hello():
    pass

class World:
    pass
""")

        (root / "module2.py").write_text("""
from pathlib import Path

def test():
    return 42
""")

        # Build index
        repo_map = RepoMap().build(root)

        # Check symbols were extracted
        assert len(repo_map.symbols) > 0

        # Should have modules, functions, and classes
        types = set(s.type for s in repo_map.symbols)
        assert "module" in types
        assert "function" in types
        assert "class" in types

        # Check specific symbols
        func_names = [s.name for s in repo_map.symbols if s.type == "function"]
        assert "hello" in func_names
        assert "test" in func_names

        class_names = [s.name for s in repo_map.symbols if s.type == "class"]
        assert "World" in class_names


def test_repomap_save_load():
    """Test RepoMap save and load roundtrip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create sample file
        (root / "test.py").write_text("""
def func1():
    pass

def func2():
    pass
""")

        # Build and save
        repo_map1 = RepoMap().build(root)
        index_path = root / "symbols.json"
        repo_map1.save(index_path)

        # Load
        repo_map2 = RepoMap.load(index_path)

        # Compare
        assert len(repo_map1.symbols) == len(repo_map2.symbols)
        assert repo_map1.stats() == repo_map2.stats()


def test_repomap_save_deterministic():
    """Test that RepoMap.save() produces deterministic output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create sample files
        (root / "a.py").write_text("def foo(): pass")
        (root / "b.py").write_text("def bar(): pass")

        # Build twice
        repo_map1 = RepoMap().build(root)
        repo_map2 = RepoMap().build(root)

        # Save both
        path1 = root / "symbols1.json"
        path2 = root / "symbols2.json"

        repo_map1.save(path1)
        repo_map2.save(path2)

        # Compare JSON content
        content1 = path1.read_text()
        content2 = path2.read_text()

        # Should be identical (deterministic)
        assert content1 == content2


def test_repomap_query_by_pattern():
    """Test RepoMap.query() with pattern matching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("""
def test_one():
    pass

def test_two():
    pass

def other():
    pass
""")

        repo_map = RepoMap().build(root)

        # Query with pattern
        results = repo_map.query(pattern="test")
        assert len(results) >= 2

        names = [s.name for s in results]
        assert "test_one" in names
        assert "test_two" in names


def test_repomap_query_by_type():
    """Test RepoMap.query() with type filter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("""
def my_func():
    pass

class MyClass:
    pass
""")

        repo_map = RepoMap().build(root)

        # Query functions
        funcs = repo_map.query(type="function")
        assert all(s.type == "function" for s in funcs)

        # Query classes
        classes = repo_map.query(type="class")
        assert all(s.type == "class" for s in classes)
        assert any(s.name == "MyClass" for s in classes)


def test_repomap_get_by_name():
    """Test RepoMap.get_by_name() exact match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("""
def unique_name():
    pass
""")

        repo_map = RepoMap().build(root)

        results = repo_map.get_by_name("unique_name")
        assert len(results) == 1
        assert results[0].name == "unique_name"


def test_repomap_get_files():
    """Test RepoMap.get_files()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "a.py").write_text("pass")
        (root / "b.py").write_text("pass")

        repo_map = RepoMap().build(root)

        files = repo_map.get_files()
        assert len(files) == 2
        assert "a.py" in files
        assert "b.py" in files


def test_repomap_get_file_symbols():
    """Test RepoMap.get_file_symbols()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("""
def func1():
    pass

def func2():
    pass
""")

        repo_map = RepoMap().build(root)

        symbols = repo_map.get_file_symbols("test.py")
        func_names = [s.name for s in symbols if s.type == "function"]

        assert "func1" in func_names
        assert "func2" in func_names


def test_repomap_stats():
    """Test RepoMap.stats()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("""
def func():
    pass

class Class:
    pass
""")

        repo_map = RepoMap().build(root)
        stats = repo_map.stats()

        assert "total_symbols" in stats
        assert "by_type" in stats
        assert "total_files" in stats
        assert stats["total_files"] == 1


def test_repomap_exclude_patterns():
    """Test that exclude patterns work."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create files
        (root / "good.py").write_text("def good(): pass")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "bad.py").write_text("def bad(): pass")

        repo_map = RepoMap().build(root)

        # Should not index __pycache__
        files = repo_map.get_files()
        assert not any("__pycache__" in f for f in files)


def test_repomap_parse_error_handling():
    """Test that RepoMap handles syntax errors gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create file with syntax error
        (root / "bad.py").write_text("def broken(")

        # Should not crash
        repo_map = RepoMap().build(root)

        # Should have skipped the bad file
        # (no symbols from bad.py except possibly a failed module entry)
        assert repo_map is not None
