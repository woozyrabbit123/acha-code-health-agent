"""Tests for package structure and distribution."""
import subprocess
import sys
from pathlib import Path
import importlib


def test_package_imports():
    """Test that all main modules are importable."""
    # Test core modules
    modules_to_test = [
        "agents.analysis_agent",
        "agents.refactor_agent",
        "agents.validation_agent",
        "utils.policy",
        "utils.logger",
        "utils.checkpoint",
        "utils.exporter",
        "utils.patcher",
        "utils.ast_cache",
        "utils.parallel_executor",
        "utils.sarif_reporter",
        "utils.html_reporter",
        "utils.import_analyzer",
    ]

    for module_name in modules_to_test:
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            assert False, f"Failed to import {module_name}: {e}"


def test_cli_module_exists():
    """Test that CLI module exists and has main function."""
    try:
        import cli
        assert hasattr(cli, "main"), "CLI module should have main() function"
    except ImportError as e:
        assert False, f"Failed to import cli module: {e}"


def test_pyproject_toml_exists():
    """Test that pyproject.toml exists and is valid."""
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists(), "pyproject.toml should exist"

    content = pyproject_path.read_text()

    # Check for required sections
    assert "[build-system]" in content, "pyproject.toml should have [build-system]"
    assert "[project]" in content, "pyproject.toml should have [project]"
    assert "name" in content, "pyproject.toml should specify package name"
    assert "version" in content, "pyproject.toml should specify version"
    assert "requires-python" in content, "pyproject.toml should specify Python version"


def test_version_in_pyproject():
    """Test that version is defined in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Extract version
    import re
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    assert match, "Version should be defined in pyproject.toml"

    version = match.group(1)
    assert version, "Version should not be empty"

    # Check version format (semantic versioning)
    version_parts = version.split(".")
    assert len(version_parts) >= 2, "Version should have at least major.minor format"


def test_required_files_exist():
    """Test that required distribution files exist."""
    required_files = [
        "README.md",
        "pyproject.toml",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
    ]

    for file_name in required_files:
        file_path = Path(file_name)
        assert file_path.exists(), f"Required file {file_name} should exist"


def test_schemas_directory_exists():
    """Test that schemas directory exists with JSON files."""
    schemas_dir = Path("schemas")
    assert schemas_dir.exists(), "schemas/ directory should exist"
    assert schemas_dir.is_dir(), "schemas/ should be a directory"

    # Check for schema files
    schema_files = list(schemas_dir.glob("*.json"))
    assert len(schema_files) > 0, "schemas/ should contain JSON schema files"


def test_github_workflows_exist():
    """Test that GitHub Actions workflows are configured."""
    workflows_dir = Path(".github/workflows")
    assert workflows_dir.exists(), ".github/workflows/ should exist"

    # Check for main CI workflow
    ci_workflow = workflows_dir / "ci.yml"
    assert ci_workflow.exists(), "CI workflow should exist"


def test_entry_point_configuration():
    """Test that entry point is correctly configured."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Check for scripts section
    assert "[project.scripts]" in content, "Should have [project.scripts] section"
    assert "acha" in content, "Should define 'acha' entry point"


def test_dependencies_specified():
    """Test that dependencies are specified in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    assert "dependencies" in content, "Should specify dependencies"
    assert "jsonschema" in content, "Should include jsonschema dependency"


def test_optional_dependencies_specified():
    """Test that optional dependencies are specified."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    assert "[project.optional-dependencies]" in content, "Should have optional dependencies"
    assert "test" in content, "Should have test dependencies"
    assert "pytest" in content, "Should include pytest in test dependencies"


def test_license_specified():
    """Test that license is specified in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    assert "license" in content.lower(), "Should specify license"
    assert "MIT" in content or "mit" in content, "Should use MIT license"


def test_python_version_requirement():
    """Test that Python version requirement is correct."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    assert "requires-python" in content, "Should specify Python version requirement"
    assert "3.11" in content, "Should require Python 3.11+"


def test_package_structure():
    """Test that package structure is correct."""
    required_dirs = [
        "agents",
        "utils",
        "schemas",
        "tests",
    ]

    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        assert dir_path.exists(), f"Required directory {dir_name} should exist"
        assert dir_path.is_dir(), f"{dir_name} should be a directory"


def test_sample_project_exists():
    """Test that sample project exists for testing."""
    sample_dir = Path("sample_project")
    assert sample_dir.exists(), "sample_project/ should exist"
    assert sample_dir.is_dir(), "sample_project should be a directory"

    # Check for Python files in sample project
    py_files = list(sample_dir.glob("*.py"))
    assert len(py_files) > 0, "sample_project should contain Python files"


def test_makefile_targets():
    """Test that Makefile has expected targets."""
    makefile_path = Path("Makefile")
    if not makefile_path.exists():
        return  # Makefile is optional

    content = makefile_path.read_text()

    expected_targets = ["test", "setup", "clean"]
    for target in expected_targets:
        assert target in content, f"Makefile should have '{target}' target"


def test_build_backend_specified():
    """Test that build backend is specified in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    assert "build-backend" in content, "Should specify build backend"
    assert "setuptools" in content, "Should use setuptools build backend"


def test_no_setup_py():
    """Test that legacy setup.py doesn't exist (modern packaging)."""
    setup_py = Path("setup.py")
    # It's OK if setup.py exists for compatibility, but pyproject.toml should be primary
    # This test just documents that we prefer pyproject.toml
    if setup_py.exists():
        # If setup.py exists, it should be minimal and reference pyproject.toml
        content = setup_py.read_text()
        assert "setuptools" in content or len(content) < 200, \
            "If setup.py exists, it should be minimal/compatibility shim"


def test_pytest_configuration():
    """Test that pytest is configured in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Check for pytest configuration
    assert "[tool.pytest" in content, "Should have pytest configuration"


def test_coverage_configuration():
    """Test that coverage is configured."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Check for coverage configuration
    assert "[tool.coverage" in content, "Should have coverage configuration"
