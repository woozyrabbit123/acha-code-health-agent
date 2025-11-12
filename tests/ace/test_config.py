"""Tests for ACE configuration system."""

import os
import tempfile
from pathlib import Path

from ace.config import (
    find_config_file,
    get_default_config,
    load_config,
    load_toml_config,
    merge_config,
    should_include_file,
)


def test_default_config():
    """Test default configuration values."""
    config = get_default_config()

    assert config.cache_ttl == 3600
    assert config.cache_dir == ".ace"
    assert config.baseline_path == ".ace/baseline.json"
    assert config.enabled_rules == []
    assert config.disabled_rules == []
    assert config.fail_on_new is False
    assert config.fail_on_regression is False
    assert "**/*.py" in config.includes
    assert "**/.venv/**" in config.excludes


def test_find_config_file():
    """Test finding ace.toml in directory hierarchy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        subdir = root / "subdir" / "nested"
        subdir.mkdir(parents=True)

        # Create ace.toml in root
        config_file = root / "ace.toml"
        config_file.write_text("[core]\n", encoding="utf-8")

        # Should find config from subdir
        found = find_config_file(subdir)
        assert found == config_file

        # Should find config from root
        found = find_config_file(root)
        assert found == config_file


def test_find_config_file_nonexistent():
    """Test find_config_file returns None when no config exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        found = find_config_file(Path(tmpdir))
        assert found is None


def test_load_toml_config():
    """Test loading TOML configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "ace.toml"
        config_file.write_text(
            """
[core]
includes = ["src/**/*.py"]
excludes = ["**/tests/**"]
cache_ttl = 7200
cache_dir = ".cache"
baseline = "baseline.json"

[rules]
enable = ["PY-*"]
disable = ["PY-I101-IMPORT-SORT"]

[ci]
fail_on_new = true
fail_on_regression = false
""",
            encoding="utf-8",
        )

        config = load_toml_config(config_file)

        assert config["core"]["includes"] == ["src/**/*.py"]
        assert config["core"]["excludes"] == ["**/tests/**"]
        assert config["core"]["cache_ttl"] == 7200
        assert config["rules"]["enable"] == ["PY-*"]
        assert config["ci"]["fail_on_new"] is True


def test_merge_config_precedence():
    """Test configuration precedence: CLI > ENV > TOML > defaults."""
    base = get_default_config()

    toml_config = {
        "core": {"cache_ttl": 1800, "cache_dir": ".toml_cache"},
        "rules": {"enable": ["PY-*"]},
    }

    env_overrides = {"cache_ttl": 2400, "cache_dir": ".env_cache"}

    cli_overrides = {"cache_ttl": 3000}

    # TOML overrides defaults
    config1 = merge_config(base, toml_config=toml_config)
    assert config1.cache_ttl == 1800
    assert config1.cache_dir == ".toml_cache"

    # ENV overrides TOML
    config2 = merge_config(base, toml_config=toml_config, env_overrides=env_overrides)
    assert config2.cache_ttl == 2400
    assert config2.cache_dir == ".env_cache"

    # CLI overrides ENV
    config3 = merge_config(
        base,
        toml_config=toml_config,
        env_overrides=env_overrides,
        cli_overrides=cli_overrides,
    )
    assert config3.cache_ttl == 3000
    assert config3.cache_dir == ".env_cache"  # CLI didn't override cache_dir


def test_load_config_with_explicit_path():
    """Test loading config with explicit path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "custom.toml"
        config_file.write_text(
            """
[core]
cache_ttl = 9999
""",
            encoding="utf-8",
        )

        config = load_config(config_path=config_file)
        assert config.cache_ttl == 9999


def test_load_config_with_env_overrides():
    """Test loading config with environment variable overrides."""
    # Set environment variables
    os.environ["ACE_CACHE_TTL"] = "5000"
    os.environ["ACE_CACHE_DIR"] = "/tmp/ace_cache"
    os.environ["ACE_BASELINE"] = "/tmp/baseline.json"

    try:
        config = load_config()

        assert config.cache_ttl == 5000
        assert config.cache_dir == "/tmp/ace_cache"
        assert config.baseline_path == "/tmp/baseline.json"
    finally:
        # Clean up environment
        os.environ.pop("ACE_CACHE_TTL", None)
        os.environ.pop("ACE_CACHE_DIR", None)
        os.environ.pop("ACE_BASELINE", None)


def test_load_config_with_cli_overrides():
    """Test loading config with CLI overrides."""
    cli_overrides = {"cache_ttl": 1200, "cache_dir": ".cli_cache"}

    config = load_config(cli_overrides=cli_overrides)

    assert config.cache_ttl == 1200
    assert config.cache_dir == ".cli_cache"


def test_should_include_file_basic():
    """Test basic file inclusion logic."""
    config = get_default_config()

    # Should include Python files
    assert should_include_file("src/test.py", config) is True

    # Should exclude .venv files
    assert should_include_file(".venv/lib/python/test.py", config) is False

    # Should exclude dist files
    assert should_include_file("dist/package/test.py", config) is False


def test_should_include_file_with_custom_patterns():
    """Test file inclusion with custom patterns."""
    config = get_default_config()
    config.includes = ["src/**/*.py", "lib/**/*.py"]
    config.excludes = ["**/test_*.py"]

    # Should include src Python files
    assert should_include_file("src/module/code.py", config) is True

    # Should include lib Python files
    assert should_include_file("lib/utils.py", config) is True

    # Should exclude test files
    assert should_include_file("src/test_module.py", config) is False

    # Should not include files outside src/lib
    assert should_include_file("other/code.py", config) is False


def test_should_include_file_windows_paths():
    """Test file inclusion with Windows-style paths."""
    config = get_default_config()
    config.includes = ["src/**/*.py"]
    config.excludes = ["**/tests/**"]

    # Windows path should be normalized
    assert should_include_file(Path("src\\module\\code.py"), config) is True
    assert should_include_file(Path("src\\tests\\test.py"), config) is False


def test_should_include_file_excludes_take_precedence():
    """Test that excludes take precedence over includes."""
    config = get_default_config()
    config.includes = ["**/*.py"]
    config.excludes = ["**/node_modules/**"]

    # Excluded even though it matches include pattern
    assert should_include_file("node_modules/package/test.py", config) is False


def test_merge_config_rules():
    """Test merging rule configurations."""
    base = get_default_config()

    toml_config = {
        "rules": {
            "enable": ["PY-S101-UNSAFE-HTTP", "PY-E201-BROAD-EXCEPT"],
            "disable": ["MD-S001-DANGEROUS-COMMAND"],
        }
    }

    config = merge_config(base, toml_config=toml_config)

    assert config.enabled_rules == ["PY-S101-UNSAFE-HTTP", "PY-E201-BROAD-EXCEPT"]
    assert config.disabled_rules == ["MD-S001-DANGEROUS-COMMAND"]


def test_merge_config_ci_flags():
    """Test merging CI configuration."""
    base = get_default_config()

    toml_config = {"ci": {"fail_on_new": True, "fail_on_regression": True}}

    config = merge_config(base, toml_config=toml_config)

    assert config.fail_on_new is True
    assert config.fail_on_regression is True


def test_load_config_autodiscovery():
    """Test automatic discovery of ace.toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create ace.toml
        config_file = Path(tmpdir) / "ace.toml"
        config_file.write_text(
            """
[core]
cache_ttl = 4321
""",
            encoding="utf-8",
        )

        # Load config from subdirectory (should autodiscover)
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()

        # Change to subdir temporarily
        original_cwd = Path.cwd()
        try:
            os.chdir(subdir)
            config = load_config()
            # Should find parent's ace.toml
            assert config.cache_ttl == 4321
        finally:
            os.chdir(original_cwd)


def test_config_partial_toml():
    """Test that partial TOML configs merge with defaults."""
    base = get_default_config()

    # Only specify cache_ttl, rest should use defaults
    toml_config = {"core": {"cache_ttl": 999}}

    config = merge_config(base, toml_config=toml_config)

    assert config.cache_ttl == 999
    assert config.cache_dir == ".ace"  # Default preserved
    assert config.baseline_path == ".ace/baseline.json"  # Default preserved


def test_config_empty_toml():
    """Test that empty TOML config uses all defaults."""
    base = get_default_config()

    toml_config = {}

    config = merge_config(base, toml_config=toml_config)

    # Should be identical to base
    assert config.cache_ttl == base.cache_ttl
    assert config.cache_dir == base.cache_dir
    assert config.includes == base.includes


def test_config_invalid_env_value():
    """Test that invalid environment variable values are ignored."""
    # Set invalid env var
    os.environ["ACE_CACHE_TTL"] = "not_a_number"

    try:
        config = load_config()
        # Should fall back to default
        assert config.cache_ttl == 3600
    finally:
        os.environ.pop("ACE_CACHE_TTL", None)
