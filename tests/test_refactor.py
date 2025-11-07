"""Tests for RefactorAgent"""
import json
import tempfile
import py_compile
from pathlib import Path
import pytest
from jsonschema import validate, ValidationError

try:
    from importlib import resources
except ImportError:
    import importlib_resources as resources

from acha.agents.analysis_agent import AnalysisAgent
from acha.agents.refactor_agent import RefactorAgent


def test_refactor_agent_inlines_constants():
    """Test that RefactorAgent inlines duplicated constants"""

    # Create a temporary directory with a test module
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_file = tmpdir_path / "test_module.py"

        # Write test code with duplicated constant
        test_code = '''"""Test module with duplicated constant"""

# Duplicated constant
API_KEY = "secret-key-123"

def get_key():
    return API_KEY

def validate_key(key):
    if key == API_KEY:
        return True
    return False

def check_access():
    if API_KEY == "secret-key-123":
        print(API_KEY)
        return True
    return False

def log_key():
    print(f"Key: {API_KEY}")
'''
        test_file.write_text(test_code)

        # First run analysis to get findings
        analysis_agent = AnalysisAgent(dup_threshold=3)
        analysis_result = analysis_agent.run(tmpdir)

        # Save analysis to temp file
        analysis_file = tmpdir_path / "analysis.json"
        with open(analysis_file, 'w') as f:
            json.dump(analysis_result, f)

        # Run refactoring
        refactor_agent = RefactorAgent()
        patch_summary = refactor_agent.apply(str(tmpdir_path), str(analysis_file))

        # Verify patch summary structure
        assert 'patch_id' in patch_summary
        assert 'files_touched' in patch_summary
        assert 'lines_added' in patch_summary
        assert 'lines_removed' in patch_summary
        assert 'notes' in patch_summary

        # Validate against schema
        schema_files = resources.files("acha.schemas")
        schema_path = schema_files.joinpath("patch_summary.schema.json")
        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)

        try:
            validate(instance=patch_summary, schema=schema)
        except ValidationError as e:
            pytest.fail(f"Patch summary does not match schema: {e}")

        # Check that diff file was created
        diff_path = Path("dist/patch.diff")
        assert diff_path.exists(), "dist/patch.diff should exist"

        # Check that workdir was created and contains modified file
        workdir_path = Path("workdir")
        assert workdir_path.exists(), "workdir should exist"

        modified_file = workdir_path / "test_module.py"
        assert modified_file.exists(), "Modified file should exist in workdir"

        # Verify modified file compiles
        try:
            py_compile.compile(str(modified_file), doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"Modified file does not compile: {e}")

        # Read modified content
        with open(modified_file, 'r') as f:
            modified_content = f.read()

        # Verify that the constant definition still exists
        assert 'API_KEY = "secret-key-123"' in modified_content, \
            "Original constant definition should be preserved"

        # Verify that some references were inlined
        assert "'secret-key-123'" in modified_content, \
            "Some constant references should be inlined"


def test_refactor_agent_empty_findings():
    """Test RefactorAgent with no dup_immutable_const findings"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_file = tmpdir_path / "simple.py"

        # Write simple code with no issues
        test_code = '''"""Simple module"""

def hello():
    return "world"
'''
        test_file.write_text(test_code)

        # Create empty analysis
        analysis_file = tmpdir_path / "analysis.json"
        with open(analysis_file, 'w') as f:
            json.dump({"findings": []}, f)

        # Run refactoring
        refactor_agent = RefactorAgent()
        patch_summary = refactor_agent.apply(str(tmpdir_path), str(analysis_file))

        # Should have empty modifications
        assert len(patch_summary['files_touched']) == 0
        assert patch_summary['lines_added'] == 0
        assert patch_summary['lines_removed'] == 0


def test_patch_summary_schema_valid():
    """Test that patch_summary.schema.json is valid"""
    schema_files = resources.files("acha.schemas")
    schema_path = schema_files.joinpath("patch_summary.schema.json")
    # Test that we can access the schema
    try:
        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
    except FileNotFoundError:
        assert False, "Schema file should exist"

    # Validate schema structure
    assert schema['$schema'] == "http://json-schema.org/draft-07/schema#"
    assert 'properties' in schema
    assert 'patch_id' in schema['properties']
    assert 'files_touched' in schema['properties']
    assert 'lines_added' in schema['properties']
    assert 'lines_removed' in schema['properties']
    assert 'notes' in schema['properties']
    assert 'required' in schema


def test_refactor_preserves_syntax():
    """Test that refactoring preserves valid Python syntax"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_file = tmpdir_path / "syntax_test.py"

        # Write code with a constant used in various contexts
        test_code = '''"""Syntax preservation test"""

MAX_SIZE = 100

def check_size(value):
    if value > MAX_SIZE:
        return False
    result = value + MAX_SIZE
    return result < MAX_SIZE * 2
'''
        test_file.write_text(test_code)

        # Run analysis
        analysis_agent = AnalysisAgent(dup_threshold=2)
        analysis_result = analysis_agent.run(tmpdir)

        # Save analysis
        analysis_file = tmpdir_path / "analysis.json"
        with open(analysis_file, 'w') as f:
            json.dump(analysis_result, f)

        # Run refactoring
        refactor_agent = RefactorAgent()
        patch_summary = refactor_agent.apply(str(tmpdir_path), str(analysis_file))

        # Check workdir file compiles
        workdir_file = Path("workdir/syntax_test.py")
        if workdir_file.exists():
            try:
                py_compile.compile(str(workdir_file), doraise=True)
            except py_compile.PyCompileError as e:
                pytest.fail(f"Refactored file has syntax errors: {e}")
