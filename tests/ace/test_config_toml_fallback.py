"""Tests for TOML fallback behavior."""
from pathlib import Path

from ace.config import load_toml_config


def test_load_missing_file_returns_empty(tmp_path: Path):
    """Test that loading a missing TOML file returns empty dict."""
    nonexistent = tmp_path / "nope.toml"
    result = load_toml_config(nonexistent)

    assert result == {}


def test_load_valid_toml(tmp_path: Path):
    """Test loading a valid TOML file."""
    config_file = tmp_path / "ace.toml"
    config_file.write_text("""
[core]
cache_ttl = 7200

[rules]
enable = ["PY-E201-BROAD-EXCEPT"]
""")

    result = load_toml_config(config_file)

    assert "core" in result
    assert result["core"]["cache_ttl"] == 7200


def test_load_invalid_toml_returns_empty(tmp_path: Path):
    """Test that loading invalid TOML returns empty dict."""
    config_file = tmp_path / "invalid.toml"
    config_file.write_text("this is not [ valid toml")

    result = load_toml_config(config_file)

    # Should return empty dict on parse error
    assert result == {}
