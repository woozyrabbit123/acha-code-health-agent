"""Tests for AnalysisAgent"""
import json
import tempfile
from pathlib import Path
import pytest
from jsonschema import validate, ValidationError

from acha.agents.analysis_agent import AnalysisAgent


def test_analysis_agent_detects_issues():
    """Test that AnalysisAgent detects duplicated constants and risky constructs"""

    # Create a temporary directory with a test module
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_module.py"

        # Write test code with both duplicated constant and risky construct
        test_code = '''"""Test module with issues"""

# Duplicated constant
NAME = "TestName"

def func1():
    return NAME

def func2():
    print(NAME)
    return NAME

def func3():
    if NAME == "TestName":
        return NAME

# Risky construct
def dangerous():
    result = eval("1+1")
    return result
'''
        test_file.write_text(test_code)

        # Run analysis
        agent = AnalysisAgent(dup_threshold=3)
        result = agent.run(tmpdir)

        # Verify result structure
        assert 'findings' in result
        assert isinstance(result['findings'], list)

        # Load and validate against schema
        try:
            from importlib import resources
        except ImportError:
            import importlib_resources as resources
        schema_files = resources.files("acha.schemas")
        schema_path = schema_files.joinpath("analysis.schema.json")
        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)

        try:
            validate(instance=result, schema=schema)
        except ValidationError as e:
            pytest.fail(f"Result does not match schema: {e}")

        # Check for specific findings
        findings = result['findings']
        finding_types = [f['finding'] for f in findings]

        # Should have at least one dup_immutable_const finding
        assert 'dup_immutable_const' in finding_types, \
            f"Expected dup_immutable_const finding, got: {finding_types}"

        # Should have at least one risky_construct finding
        assert 'risky_construct' in finding_types, \
            f"Expected risky_construct finding, got: {finding_types}"

        # Verify finding structure
        for finding in findings:
            assert 'id' in finding
            assert 'file' in finding
            assert 'start_line' in finding
            assert 'end_line' in finding
            assert 'finding' in finding
            assert 'severity' in finding
            assert 'fix_type' in finding
            assert 'rationale' in finding
            assert 'test_hints' in finding
            assert isinstance(finding['test_hints'], list)
            assert 0 <= finding['severity'] <= 1


def test_analysis_agent_empty_directory():
    """Test that AnalysisAgent handles empty directories"""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = AnalysisAgent()
        result = agent.run(tmpdir)

        assert 'findings' in result
        assert len(result['findings']) == 0


def test_analysis_agent_risky_constructs():
    """Test detection of various risky constructs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "risky.py"

        test_code = '''"""Test risky constructs"""
import subprocess

def use_eval():
    eval("1+1")

def use_exec():
    exec("print('hello')")

def use_subprocess():
    subprocess.run(["ls"])
'''
        test_file.write_text(test_code)

        agent = AnalysisAgent()
        result = agent.run(tmpdir)

        findings = result['findings']
        risky_findings = [f for f in findings if f['finding'] == 'risky_construct']

        # Should detect eval, exec, and subprocess import
        assert len(risky_findings) >= 3, \
            f"Expected at least 3 risky construct findings, got {len(risky_findings)}"

        # Check severity is high for risky constructs
        for finding in risky_findings:
            assert finding['severity'] >= 0.8, \
                f"Risky construct should have high severity, got {finding['severity']}"


def test_schema_validation():
    """Test that the analysis schema is valid"""
    try:
        from importlib import resources
    except ImportError:
        import importlib_resources as resources
    schema_files = resources.files("acha.schemas")
    schema_path = schema_files.joinpath("analysis.schema.json")

    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    # Validate schema structure
    assert schema['$schema'] == "http://json-schema.org/draft-07/schema#"
    assert 'properties' in schema
    assert 'findings' in schema['properties']
    assert 'required' in schema
    assert 'findings' in schema['required']
