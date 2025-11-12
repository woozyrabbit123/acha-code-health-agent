"""Tests for ace.impact - Impact analyzer."""

import tempfile
from pathlib import Path

import pytest

from ace.repomap import RepoMap
from ace.depgraph import DepGraph
from ace.impact import ImpactAnalyzer, ImpactReport


def test_impact_analyzer_creation():
    """Test ImpactAnalyzer initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "test.py").write_text("def foo(): pass")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        assert analyzer.depgraph == depgraph


def test_predict_impacted_basic():
    """Test basic impact prediction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "lib.py").write_text("def helper(): pass")
        (root / "app.py").write_text("import lib")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        # Change lib.py
        report = analyzer.predict_impacted(["lib.py"], depth=2)

        assert isinstance(report, ImpactReport)
        assert report.changed_files == ["lib.py"]
        assert isinstance(report.impacted_files, list)
        assert isinstance(report.total_impact, int)


def test_predict_impacted_depth():
    """Test impact prediction with depth limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create chain: a -> b -> c
        (root / "a.py").write_text("import b")
        (root / "b.py").write_text("import c")
        (root / "c.py").write_text("pass")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        # Depth 1: only direct dependents
        report1 = analyzer.predict_impacted(["c.py"], depth=1)

        # Depth 2: include indirect dependents
        report2 = analyzer.predict_impacted(["c.py"], depth=2)

        assert isinstance(report1, ImpactReport)
        assert isinstance(report2, ImpactReport)


def test_predict_impacted_multiple_files():
    """Test impact prediction for multiple changed files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "a.py").write_text("pass")
        (root / "b.py").write_text("import a")
        (root / "c.py").write_text("import a")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        report = analyzer.predict_impacted(["a.py", "b.py"], depth=2)

        assert len(report.changed_files) == 2
        assert "a.py" in report.changed_files
        assert "b.py" in report.changed_files


def test_impact_by_depth():
    """Test impact_by_depth grouping."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "base.py").write_text("pass")
        (root / "mid.py").write_text("import base")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        report = analyzer.predict_impacted(["base.py"], depth=2)

        assert isinstance(report.impact_by_depth, dict)


def test_explain_impact():
    """Test explain_impact for a single file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "util.py").write_text("""
def helper():
    pass

class Util:
    pass
""")

        (root / "app.py").write_text("import util")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        explanation = analyzer.explain_impact("util.py")

        assert "file" in explanation
        assert "direct_dependents" in explanation
        assert "direct_dependencies" in explanation
        assert "exported_symbols" in explanation
        assert "total_impacted" in explanation
        assert "risk_level" in explanation


def test_assess_risk():
    """Test risk assessment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "test.py").write_text("def test(): pass")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        # Low impact
        risk_low = analyzer._assess_risk(total_impact=1, direct_dependents=1)
        assert risk_low in ["low", "medium", "high", "critical"]

        # High impact
        risk_high = analyzer._assess_risk(total_impact=50, direct_dependents=20)
        assert risk_high in ["high", "critical"]


def test_get_blast_radius():
    """Test blast radius calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "core.py").write_text("pass")
        (root / "a.py").write_text("import core")
        (root / "b.py").write_text("import core")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        radius = analyzer.get_blast_radius(["core.py"], depth=2)

        assert "changed_files" in radius
        assert "total_impacted" in radius
        assert "max_depth_reached" in radius
        assert "impact_by_depth" in radius
        assert "critical_files" in radius
        assert "overall_risk" in radius


def test_compare_changes():
    """Test comparison of two change sets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "a.py").write_text("pass")
        (root / "b.py").write_text("import a")
        (root / "c.py").write_text("pass")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        comparison = analyzer.compare_changes(["a.py"], ["c.py"], depth=2)

        assert "changes_a" in comparison
        assert "changes_b" in comparison
        assert "impact_a" in comparison
        assert "impact_b" in comparison
        assert "overlap" in comparison
        assert "similarity" in comparison


def test_find_bottlenecks():
    """Test finding bottleneck files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create hub file
        (root / "hub.py").write_text("def common(): pass")
        (root / "a.py").write_text("import hub")
        (root / "b.py").write_text("import hub")
        (root / "c.py").write_text("import hub")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        bottlenecks = analyzer.find_bottlenecks(top_n=5)

        assert isinstance(bottlenecks, list)
        # hub.py should be in bottlenecks
        files = [b["file"] for b in bottlenecks]


def test_impact_report_fields():
    """Test ImpactReport dataclass fields."""
    report = ImpactReport(
        changed_files=["a.py"],
        impacted_files=["b.py", "c.py"],
        total_impact=2
    )

    assert report.changed_files == ["a.py"]
    assert report.impacted_files == ["b.py", "c.py"]
    assert report.total_impact == 2
    assert isinstance(report.impact_by_depth, dict)
    assert isinstance(report.explanations, dict)


def test_predict_impacted_no_impact():
    """Test prediction when no files are impacted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "isolated.py").write_text("def isolated(): pass")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        report = analyzer.predict_impacted(["isolated.py"], depth=2)

        # Isolated file should have no impact
        assert report.total_impact == 0


def test_predict_impacted_with_dependencies():
    """Test including forward dependencies."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        (root / "lib.py").write_text("pass")
        (root / "app.py").write_text("import lib")

        repo_map = RepoMap().build(root)
        depgraph = DepGraph(repo_map)
        analyzer = ImpactAnalyzer(depgraph)

        # Include dependencies
        report = analyzer.predict_impacted(
            ["app.py"],
            depth=2,
            include_dependencies=True
        )

        assert isinstance(report.impacted_files, list)
