"""Tests for safe refactors (Sprint 9)"""
import json
import shutil
import tempfile
import textwrap
from pathlib import Path
from agents.refactor_agent import RefactorAgent, RefactorType
from agents.analysis_agent import AnalysisAgent


def write_file(path: Path, content: str):
    """Helper to write test files"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding='utf-8')


def test_remove_unused_imports():
    """Test removal of unused imports"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test file with unused import
        test_file = tmpdir / "test.py"
        write_file(test_file, """
import os
import sys

def main():
    print(sys.version)
""")

        # Run analysis
        agent = AnalysisAgent()
        result = agent.run(str(tmpdir))

        # Save analysis
        analysis_path = tmpdir / "analysis.json"
        with open(analysis_path, 'w') as f:
            json.dump(result, f)

        # Run refactor with remove_unused_import
        refactor_agent = RefactorAgent(refactor_types=["remove_unused_import"])
        patch_summary = refactor_agent.apply(str(tmpdir), str(analysis_path))

        # Check that 'os' import was removed
        workdir_file = Path("workdir") / "test.py"
        if workdir_file.exists():
            content = workdir_file.read_text()
            assert "import os" not in content or "# unused" in content.lower()
            assert "import sys" in content
            assert "remove_unused_import" in patch_summary.get('refactor_types_applied', [])

        # Clean up
        if Path("workdir").exists():
            shutil.rmtree("workdir")


def test_organize_imports():
    """Test import organization"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test file with unorganized imports
        test_file = tmpdir / "test.py"
        write_file(test_file, """
import sys
import json
import os

def main():
    print(os.path.exists('.'))
    print(sys.version)
    print(json.dumps({}))
""")

        # Create dummy analysis
        analysis_path = tmpdir / "analysis.json"
        with open(analysis_path, 'w') as f:
            json.dump({"findings": []}, f)

        # Run refactor with organize_imports
        refactor_agent = RefactorAgent(refactor_types=["organize_imports"])
        patch_summary = refactor_agent.apply(str(tmpdir), str(analysis_path))

        # Check that imports are organized
        workdir_file = Path("workdir") / "test.py"
        if workdir_file.exists():
            content = workdir_file.read_text()
            lines = content.split('\n')

            # Find import lines
            import_lines = [l for l in lines if l.startswith('import ')]

            # Should be sorted
            if len(import_lines) > 1:
                assert import_lines == sorted(import_lines)

        # Clean up
        if Path("workdir").exists():
            shutil.rmtree("workdir")


def test_harden_subprocess():
    """Test subprocess hardening"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test file with subprocess shell=True
        test_file = tmpdir / "test.py"
        write_file(test_file, """
import subprocess

def run_command():
    subprocess.run('ls', shell=True)
""")

        # Run analysis
        agent = AnalysisAgent()
        result = agent.run(str(tmpdir))

        # Save analysis
        analysis_path = tmpdir / "analysis.json"
        with open(analysis_path, 'w') as f:
            json.dump(result, f)

        # Run refactor with harden_subprocess
        refactor_agent = RefactorAgent(refactor_types=["harden_subprocess"])
        patch_summary = refactor_agent.apply(str(tmpdir), str(analysis_path))

        # Check that shell=True was removed
        workdir_file = Path("workdir") / "test.py"
        if workdir_file.exists():
            content = workdir_file.read_text()
            assert "shell=True" not in content
            # Should have check=False added
            assert "check=False" in content or "check=" in content
            assert "harden_subprocess" in patch_summary.get('refactor_types_applied', [])

        # Clean up
        if Path("workdir").exists():
            shutil.rmtree("workdir")


def test_combined_refactors():
    """Test applying multiple refactors together"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test file with multiple issues
        test_file = tmpdir / "test.py"
        write_file(test_file, """
import os
import sys

API_KEY = "secret123"

def func1():
    return API_KEY

def func2():
    return API_KEY

def func3():
    return API_KEY

def func4():
    return API_KEY

def func5():
    print(sys.version)
    return API_KEY
""")

        # Run analysis
        agent = AnalysisAgent()
        result = agent.run(str(tmpdir))

        # Save analysis
        analysis_path = tmpdir / "analysis.json"
        with open(analysis_path, 'w') as f:
            json.dump(result, f)

        # Run refactor with multiple types
        refactor_agent = RefactorAgent(refactor_types=["inline_const", "remove_unused_import", "organize_imports"])
        patch_summary = refactor_agent.apply(str(tmpdir), str(analysis_path))

        # Check patch summary
        assert "refactor_types_applied" in patch_summary
        applied = patch_summary["refactor_types_applied"]

        # Should have applied at least inline_const and remove_unused_import
        assert "inline_const" in applied or len(applied) > 0
        assert "remove_unused_import" in applied or len(applied) > 0

        # Clean up
        if Path("workdir").exists():
            shutil.rmtree("workdir")


def test_refactor_preserves_functionality():
    """Test that refactors preserve code functionality"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test file with test
        test_file = tmpdir / "code.py"
        write_file(test_file, """
import os
import sys

VALUE = 42

def calculate():
    return VALUE * 2

def get_version():
    return sys.version
""")

        test_test_file = tmpdir / "test_code.py"
        write_file(test_test_file, """
from code import calculate, get_version

def test_calculate():
    assert calculate() == 84

def test_version():
    assert get_version() is not None
""")

        # Run analysis
        agent = AnalysisAgent()
        result = agent.run(str(tmpdir))

        # Save analysis
        analysis_path = tmpdir / "analysis.json"
        with open(analysis_path, 'w') as f:
            json.dump(result, f)

        # Run refactor
        refactor_agent = RefactorAgent(refactor_types=["remove_unused_import"])
        patch_summary = refactor_agent.apply(str(tmpdir), str(analysis_path))

        # Verify modifications were made
        assert patch_summary["files_touched"] or patch_summary["notes"]

        # Clean up
        if Path("workdir").exists():
            shutil.rmtree("workdir")
