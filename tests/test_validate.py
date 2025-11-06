"""Tests for ValidationAgent"""
import json
import tempfile
from pathlib import Path
import pytest
from jsonschema import validate as json_validate, ValidationError

from agents.validation_agent import ValidationAgent
from utils.checkpoint import checkpoint, restore


def test_validation_agent_passing_tests():
    """Test ValidationAgent with passing tests"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a simple passing test
        test_file = tmpdir_path / "test_sample.py"
        test_code = '''"""Sample passing test"""

def test_addition():
    assert 1 + 1 == 2

def test_string():
    assert "hello" == "hello"
'''
        test_file.write_text(test_code)

        # Run validation
        agent = ValidationAgent()
        result = agent.run(str(tmpdir_path), patch_id="test-patch-001")

        # Verify result structure
        assert 'patch_id' in result
        assert 'status' in result
        assert 'duration_s' in result
        assert 'tests_run' in result
        assert 'failing_tests' in result

        # Validate against schema
        schema_path = Path("schemas/validate.schema.json")
        with open(schema_path) as f:
            schema = json.load(f)

        try:
            json_validate(instance=result, schema=schema)
        except ValidationError as e:
            pytest.fail(f"Result does not match schema: {e}")

        # Check passing status
        assert result['status'] == 'pass', f"Expected pass, got {result['status']}"
        assert result['tests_run'] >= 1, "Should have run at least 1 test"
        assert len(result['failing_tests']) == 0, "Should have no failing tests"
        assert result['patch_id'] == "test-patch-001"

        # Verify result includes validate_dir
        assert 'validate_dir' in result, "Result should include validate_dir"
        assert result['validate_dir'] == str(tmpdir_path), "validate_dir should match input directory"


def test_validation_agent_failing_tests():
    """Test ValidationAgent with failing tests and checkpoint restore"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a marker file to track restoration
        marker_file = tmpdir_path / "marker.txt"
        original_marker_content = "ORIGINAL_SNAPSHOT_DATA"
        marker_file.write_text(original_marker_content)

        # Create a module with actual code
        code_file = tmpdir_path / "calculator.py"
        code_content = '''"""Calculator module"""

def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
'''
        code_file.write_text(code_content)

        # Create a failing test
        test_file = tmpdir_path / "test_calculator.py"
        test_code = '''"""Calculator tests"""
from calculator import add, multiply

def test_add():
    assert add(2, 3) == 5

def test_multiply():
    # This test will fail
    assert multiply(2, 3) == 7  # Wrong: should be 6
'''
        test_file.write_text(test_code)

        # Create checkpoint BEFORE any modifications
        checkpoint_path = tmpdir_path / ".checkpoint"
        checkpoint(str(tmpdir_path), str(checkpoint_path))

        # Modify the marker file (simulate changes during validation)
        marker_file.write_text("MODIFIED_DURING_RUN")

        # Modify the code file (simulate a bad refactor)
        code_file.write_text('''"""Calculator module - broken"""

def add(a, b):
    return a - b  # BROKEN

def multiply(a, b):
    return a * b
''')

        # Run validation
        agent = ValidationAgent()
        result = agent.run(str(tmpdir_path), patch_id="test-patch-002")

        # Check failing status
        assert result['status'] == 'fail', f"Expected fail, got {result['status']}"
        assert result['tests_run'] >= 1, "Should have run at least 1 test"
        assert len(result['failing_tests']) > 0, "Should have failing tests"
        assert result['patch_id'] == "test-patch-002"

        # Verify result includes validate_dir
        assert 'validate_dir' in result, "Result should include validate_dir"
        assert result['validate_dir'] == str(tmpdir_path), "validate_dir should match input directory"

        # Restore from checkpoint to the SAME directory
        restore(str(checkpoint_path), str(tmpdir_path))

        # Verify restoration - marker file should be back to original
        with open(marker_file, 'r') as f:
            restored_marker = f.read()

        assert restored_marker == original_marker_content, \
            f"Marker file should be restored. Expected '{original_marker_content}', got '{restored_marker}'"

        # Verify code file restoration
        with open(code_file, 'r') as f:
            restored_content = f.read()

        assert 'return a + b' in restored_content, "Should be restored to original"
        assert 'return a - b' not in restored_content, "Should not have broken code"


def test_validation_schema_valid():
    """Test that validate.schema.json is valid"""
    schema_path = Path("schemas/validate.schema.json")
    assert schema_path.exists(), "Schema file should exist"

    with open(schema_path) as f:
        schema = json.load(f)

    # Validate schema structure
    assert schema['$schema'] == "http://json-schema.org/draft-07/schema#"
    assert 'properties' in schema
    assert 'patch_id' in schema['properties']
    assert 'status' in schema['properties']
    assert 'duration_s' in schema['properties']
    assert 'tests_run' in schema['properties']
    assert 'failing_tests' in schema['properties']
    assert 'required' in schema
    assert 'patch_id' in schema['required']


def test_checkpoint_and_restore():
    """Test checkpoint and restore functionality"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create some files
        file1 = tmpdir_path / "file1.txt"
        file1.write_text("original content 1")

        file2 = tmpdir_path / "file2.txt"
        file2.write_text("original content 2")

        # Create checkpoint
        checkpoint_path = tmpdir_path / ".backup"
        checkpoint(str(tmpdir_path), str(checkpoint_path))

        # Modify files
        file1.write_text("modified content 1")
        file2.write_text("modified content 2")

        # Verify modification
        assert file1.read_text() == "modified content 1"
        assert file2.read_text() == "modified content 2"

        # Restore from checkpoint
        restore(str(checkpoint_path), str(tmpdir_path))

        # Verify restoration
        assert file1.read_text() == "original content 1"
        assert file2.read_text() == "original content 2"


def test_validation_agent_with_no_tests():
    """Test ValidationAgent with directory containing no tests"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a non-test file
        code_file = tmpdir_path / "sample.py"
        code_file.write_text("# Just a file, no tests")

        # Run validation
        agent = ValidationAgent()
        result = agent.run(str(tmpdir_path), patch_id="test-patch-003")

        # Should run but find 0 tests
        assert 'patch_id' in result
        assert result['patch_id'] == "test-patch-003"
        # Status depends on pytest behavior with no tests
        assert result['tests_run'] >= 0


def test_validator_ignores_parent_pytest_ini():
    """Test that ValidationAgent ignores parent directory pytest.ini"""

    # Save current repo pytest.ini content if it exists
    repo_pytest_ini = Path("pytest.ini")
    original_content = None
    if repo_pytest_ini.exists():
        with open(repo_pytest_ini, 'r') as f:
            original_content = f.read()

    try:
        # Create a misleading pytest.ini at repo root
        misleading_config = "[pytest]\ntestpaths = nonexistent_dir\n"
        with open(repo_pytest_ini, 'w') as f:
            f.write(misleading_config)

        # Create a temp target project with a passing test
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            test_file = tmpdir_path / "test_isolated.py"
            test_code = '''"""Isolated test"""

def test_passes():
    assert True

def test_also_passes():
    assert 1 + 1 == 2
'''
            test_file.write_text(test_code)

            # Run validation - should find and run tests in tmpdir only
            agent = ValidationAgent()
            result = agent.run(str(tmpdir_path), patch_id="test-patch-isolation")

            # Verify it ran the tests successfully
            assert result['status'] == 'pass', \
                f"Expected pass, got {result['status']}. Validator may be leaking to parent pytest.ini"
            assert result['tests_run'] >= 1, \
                f"Expected at least 1 test, got {result['tests_run']}. Validator may be using parent config"
            assert result['patch_id'] == "test-patch-isolation"

    finally:
        # Restore original pytest.ini
        if original_content is not None:
            with open(repo_pytest_ini, 'w') as f:
                f.write(original_content)
        elif repo_pytest_ini.exists():
            repo_pytest_ini.unlink()
