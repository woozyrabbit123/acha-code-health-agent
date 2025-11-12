"""ACE configuration management with precedence handling."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for Python 3.9-3.10


@dataclass
class ACEConfig:
    """
    ACE configuration with defaults.

    Precedence: CLI args > Environment > ace.toml > defaults
    """

    # Core settings
    includes: list[str]
    excludes: list[str]
    cache_ttl: int
    cache_dir: str
    baseline_path: str

    # Rules
    enabled_rules: list[str]
    disabled_rules: list[str]

    # CI settings
    fail_on_new: bool
    fail_on_regression: bool


def get_default_config() -> ACEConfig:
    """
    Get default configuration.

    Returns:
        ACEConfig with default values
    """
    return ACEConfig(
        includes=["**/*.py", "**/*.md", "**/*.yml", "**/*.yaml", "**/*.sh"],
        excludes=["**/.venv/**", "**/venv/**", "**/dist/**", "**/.git/**", "**/node_modules/**"],
        cache_ttl=3600,
        cache_dir=".ace",
        baseline_path=".ace/baseline.json",
        enabled_rules=[],  # Empty means all rules
        disabled_rules=[],
        fail_on_new=False,
        fail_on_regression=False,
    )


def find_config_file(start_path: Path | None = None) -> Path | None:
    """
    Find ace.toml in current directory or parent directories.

    Args:
        start_path: Starting directory (default: current directory)

    Returns:
        Path to ace.toml if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Search up to root
    while True:
        config_path = current / "ace.toml"
        if config_path.exists():
            return config_path

        # Stop at root
        if current.parent == current:
            break

        current = current.parent

    return None


def load_toml_config(config_path: Path) -> dict[str, Any]:
    """
    Load configuration from ace.toml file.

    Args:
        config_path: Path to ace.toml

    Returns:
        Parsed TOML configuration
    """
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def merge_config(
    base: ACEConfig,
    toml_config: dict[str, Any] | None = None,
    env_overrides: dict[str, Any] | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> ACEConfig:
    """
    Merge configurations with precedence: CLI > ENV > TOML > defaults.

    Args:
        base: Base configuration (usually defaults)
        toml_config: Configuration from ace.toml
        env_overrides: Overrides from environment variables
        cli_overrides: Overrides from CLI arguments

    Returns:
        Merged ACEConfig
    """
    # Start with base
    config_dict = {
        "includes": base.includes[:],
        "excludes": base.excludes[:],
        "cache_ttl": base.cache_ttl,
        "cache_dir": base.cache_dir,
        "baseline_path": base.baseline_path,
        "enabled_rules": base.enabled_rules[:],
        "disabled_rules": base.disabled_rules[:],
        "fail_on_new": base.fail_on_new,
        "fail_on_regression": base.fail_on_regression,
    }

    # Apply TOML config
    if toml_config:
        if "core" in toml_config:
            core = toml_config["core"]
            if "includes" in core:
                config_dict["includes"] = core["includes"]
            if "excludes" in core:
                config_dict["excludes"] = core["excludes"]
            if "cache_ttl" in core:
                config_dict["cache_ttl"] = core["cache_ttl"]
            if "cache_dir" in core:
                config_dict["cache_dir"] = core["cache_dir"]
            if "baseline" in core:
                config_dict["baseline_path"] = core["baseline"]

        if "rules" in toml_config:
            rules = toml_config["rules"]
            if "enable" in rules:
                config_dict["enabled_rules"] = rules["enable"]
            if "disable" in rules:
                config_dict["disabled_rules"] = rules["disable"]

        if "ci" in toml_config:
            ci = toml_config["ci"]
            if "fail_on_new" in ci:
                config_dict["fail_on_new"] = ci["fail_on_new"]
            if "fail_on_regression" in ci:
                config_dict["fail_on_regression"] = ci["fail_on_regression"]

    # Apply environment overrides
    if env_overrides:
        for key, value in env_overrides.items():
            if value is not None and key in config_dict:
                config_dict[key] = value

    # Apply CLI overrides (highest precedence)
    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is not None and key in config_dict:
                config_dict[key] = value

    return ACEConfig(**config_dict)


def load_config(
    config_path: Path | str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> ACEConfig:
    """
    Load ACE configuration with full precedence handling.

    Precedence: CLI > ENV > ace.toml > defaults

    Args:
        config_path: Explicit path to ace.toml (from --config flag)
        cli_overrides: Overrides from CLI arguments

    Returns:
        Merged ACEConfig
    """
    # Start with defaults
    config = get_default_config()

    # Find and load ace.toml
    toml_config = None
    if config_path:
        # Explicit config path from CLI
        config_file = Path(config_path)
        if config_file.exists():
            toml_config = load_toml_config(config_file)
    else:
        # Auto-discover ace.toml
        config_file = find_config_file()
        if config_file:
            toml_config = load_toml_config(config_file)

    # Collect environment overrides
    env_overrides = {}
    if "ACE_CACHE_TTL" in os.environ:
        try:
            env_overrides["cache_ttl"] = int(os.environ["ACE_CACHE_TTL"])
        except ValueError:
            pass
    if "ACE_CACHE_DIR" in os.environ:
        env_overrides["cache_dir"] = os.environ["ACE_CACHE_DIR"]
    if "ACE_BASELINE" in os.environ:
        env_overrides["baseline_path"] = os.environ["ACE_BASELINE"]

    # Merge with precedence
    return merge_config(config, toml_config, env_overrides, cli_overrides)


def should_include_file(file_path: Path | str, config: ACEConfig) -> bool:
    """
    Check if file should be included based on config patterns.

    Args:
        file_path: File path to check
        config: ACE configuration

    Returns:
        True if file matches includes and not in excludes
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)

    # Normalize path for matching (use forward slashes)
    path_str = str(file_path).replace("\\", "/")

    # Check excludes first (more specific)
    for exclude_pattern in config.excludes:
        if _matches_pattern(path_str, exclude_pattern):
            return False

    # Check includes
    for include_pattern in config.includes:
        if _matches_pattern(path_str, include_pattern):
            return True

    return False


def _matches_pattern(path: str, pattern: str) -> bool:
    """
    Simple glob pattern matching.

    Supports:
    - ** for recursive directories
    - * for wildcards within path components
    - Exact matches

    Args:
        path: File path (normalized with forward slashes)
        pattern: Glob pattern

    Returns:
        True if path matches pattern
    """
    from fnmatch import fnmatch

    # Handle ** recursive patterns
    if "**" in pattern:
        # Convert ** to match any depth
        parts = pattern.split("/")
        if parts[0] == "**":
            # **/*.py matches any .py file at any depth
            remaining = "/".join(parts[1:])
            return any(
                fnmatch(path_part, remaining)
                for path_part in [path] + [
                    "/".join(path.split("/")[i:]) for i in range(1, len(path.split("/")))
                ]
            )

    # Simple fnmatch for patterns without **
    return fnmatch(path, pattern) or fnmatch(path.split("/")[-1], pattern)
