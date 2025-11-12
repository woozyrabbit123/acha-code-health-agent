"""Tests for policy configuration module."""

import tempfile
from pathlib import Path

import pytest

from ace.policy_config import (
    PolicyConfig,
    aggregate_findings_by_risk_class,
    get_exit_code_from_policy,
    load_policy_config,
    policy_hash,
    validate_policy_config,
)


class TestPolicyConfig:
    """Tests for PolicyConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = PolicyConfig()

        assert config.version == "0.7.0"
        assert config.alpha == 0.7
        assert config.beta == 0.3
        assert config.gamma == 0.2
        assert config.auto_threshold == 0.70
        assert config.suggest_threshold == 0.50
        assert config.max_findings == 0
        assert config.fail_on_critical is True

    def test_get_mode_default(self):
        """Test get_mode returns default."""
        config = PolicyConfig()
        assert config.get_mode("UNKNOWN-RULE") == "auto-fix"

    def test_get_mode_configured(self):
        """Test get_mode returns configured mode."""
        config = PolicyConfig(modes={"RULE-1": "detect-only"})
        assert config.get_mode("RULE-1") == "detect-only"

    def test_is_auto_fix(self):
        """Test is_auto_fix check."""
        config = PolicyConfig(modes={
            "RULE-1": "auto-fix",
            "RULE-2": "detect-only",
        })

        assert config.is_auto_fix("RULE-1") is True
        assert config.is_auto_fix("RULE-2") is False
        assert config.is_auto_fix("RULE-3") is True  # default

    def test_get_risk_class(self):
        """Test get_risk_class lookup."""
        config = PolicyConfig(risk_classes={
            "security": ["RULE-1", "RULE-2"],
            "reliability": ["RULE-3"],
        })

        assert config.get_risk_class("RULE-1") == "security"
        assert config.get_risk_class("RULE-3") == "reliability"
        assert config.get_risk_class("RULE-UNKNOWN") is None

    def test_is_suppressed_global(self):
        """Test global path suppression."""
        config = PolicyConfig(suppressions_paths=["tests/**", "**/test_*.py"])

        assert config.is_suppressed("tests/test_foo.py", "RULE-1") is True
        assert config.is_suppressed("src/test_bar.py", "RULE-1") is True
        assert config.is_suppressed("src/main.py", "RULE-1") is False

    def test_is_suppressed_rule_specific(self):
        """Test rule-specific suppression."""
        config = PolicyConfig(suppressions_rules={
            "RULE-1": ["scripts/**"],
            "RULE-2": ["tools/**"],
        })

        assert config.is_suppressed("scripts/foo.py", "RULE-1") is True
        assert config.is_suppressed("scripts/foo.py", "RULE-2") is False
        assert config.is_suppressed("tools/bar.py", "RULE-2") is True


class TestLoadPolicyConfig:
    """Tests for loading policy from TOML."""

    def test_load_nonexistent_file(self):
        """Test loading non-existent file returns default config."""
        config = load_policy_config("/nonexistent/policy.toml")
        assert config.version == "0.7.0"  # default

    def test_load_valid_toml(self):
        """Test loading valid TOML config."""
        toml_content = """
[meta]
version = "0.7.0"
description = "Test policy"

[scoring]
alpha = 0.8
beta = 0.2
gamma = 0.3

[limits]
max_findings = 100
fail_on_critical = false

[modes]
"RULE-1" = "detect-only"

[risk_classes]
security = ["RULE-1", "RULE-2"]
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            path = Path(f.name)

        try:
            config = load_policy_config(path)

            assert config.version == "0.7.0"
            assert config.alpha == 0.8
            assert config.beta == 0.2
            assert config.gamma == 0.3
            assert config.max_findings == 100
            assert config.fail_on_critical is False
            assert config.modes["RULE-1"] == "detect-only"
            assert "security" in config.risk_classes
        finally:
            path.unlink()

    def test_load_invalid_toml(self):
        """Test loading invalid TOML raises error."""
        toml_content = """
[invalid syntax
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Failed to parse"):
                load_policy_config(path)
        finally:
            path.unlink()


class TestValidatePolicyConfig:
    """Tests for policy config validation."""

    def test_valid_config(self):
        """Test that valid config passes validation."""
        config = PolicyConfig()
        validate_policy_config(config)  # Should not raise

    def test_invalid_alpha(self):
        """Test that invalid alpha fails validation."""
        config = PolicyConfig(alpha=1.5)
        with pytest.raises(ValueError, match="alpha must be in"):
            validate_policy_config(config)

    def test_invalid_beta(self):
        """Test that invalid beta fails validation."""
        config = PolicyConfig(beta=-0.1)
        with pytest.raises(ValueError, match="beta must be in"):
            validate_policy_config(config)

    def test_invalid_thresholds(self):
        """Test that invalid thresholds fail validation."""
        config = PolicyConfig(auto_threshold=0.5, suggest_threshold=0.7)
        with pytest.raises(ValueError, match="auto_threshold.*must be >="):
            validate_policy_config(config)

    def test_invalid_mode(self):
        """Test that invalid mode fails validation."""
        config = PolicyConfig(modes={"RULE-1": "invalid-mode"})
        with pytest.raises(ValueError, match="Invalid mode"):
            validate_policy_config(config)

    def test_invalid_max_findings(self):
        """Test that negative max_findings fails validation."""
        config = PolicyConfig(max_findings=-1)
        with pytest.raises(ValueError, match="max_findings must be"):
            validate_policy_config(config)


class TestPolicyHash:
    """Tests for policy hash computation."""

    def test_deterministic(self):
        """Test that policy hash is deterministic."""
        config = PolicyConfig(raw_config={"test": "value"})
        hash1 = policy_hash(config)
        hash2 = policy_hash(config)
        assert hash1 == hash2

    def test_different_configs(self):
        """Test that different configs have different hashes."""
        config1 = PolicyConfig(raw_config={"test": "value1"})
        config2 = PolicyConfig(raw_config={"test": "value2"})
        hash1 = policy_hash(config1)
        hash2 = policy_hash(config2)
        assert hash1 != hash2


class TestAggregateFindingsByRiskClass:
    """Tests for finding aggregation by risk class."""

    def test_empty_findings(self):
        """Test with no findings."""
        policy = PolicyConfig()
        counts = aggregate_findings_by_risk_class([], policy)
        assert counts == {}

    def test_categorized_findings(self):
        """Test findings are categorized correctly."""
        policy = PolicyConfig(risk_classes={
            "security": ["RULE-1", "RULE-2"],
            "reliability": ["RULE-3"],
        })

        findings = [
            {"rule": "RULE-1", "severity": "high"},
            {"rule": "RULE-1", "severity": "high"},
            {"rule": "RULE-3", "severity": "medium"},
        ]

        counts = aggregate_findings_by_risk_class(findings, policy)

        assert counts["security"] == 2
        assert counts["reliability"] == 1

    def test_uncategorized_findings(self):
        """Test uncategorized findings."""
        policy = PolicyConfig(risk_classes={
            "security": ["RULE-1"],
        })

        findings = [
            {"rule": "RULE-1", "severity": "high"},
            {"rule": "RULE-UNKNOWN", "severity": "low"},
        ]

        counts = aggregate_findings_by_risk_class(findings, policy)

        assert counts["security"] == 1
        assert counts["uncategorized"] == 1


class TestGetExitCodeFromPolicy:
    """Tests for exit code determination."""

    def test_success(self):
        """Test success case."""
        policy = PolicyConfig()
        findings = []
        code, messages = get_exit_code_from_policy(findings, policy)

        assert code == 0
        assert messages == []

    def test_critical_findings(self):
        """Test critical findings trigger exit code 2."""
        policy = PolicyConfig(fail_on_critical=True)
        findings = [{"severity": "critical", "rule": "TEST"}]
        code, messages = get_exit_code_from_policy(findings, policy)

        assert code == 2
        assert len(messages) == 1
        assert "critical" in messages[0]

    def test_warn_threshold(self):
        """Test warning threshold triggers exit code 1."""
        policy = PolicyConfig(warn_at=5, fail_at=10)
        findings = [{"severity": "low", "rule": "TEST"}] * 6
        code, messages = get_exit_code_from_policy(findings, policy)

        assert code == 1
        assert len(messages) == 1
        assert "warn_at" in messages[0]

    def test_fail_threshold(self):
        """Test failure threshold triggers exit code 2."""
        policy = PolicyConfig(warn_at=5, fail_at=10)
        findings = [{"severity": "low", "rule": "TEST"}] * 11
        code, messages = get_exit_code_from_policy(findings, policy)

        assert code == 2
        assert len(messages) == 1
        assert "fail_at" in messages[0]

    def test_max_findings(self):
        """Test max_findings limit."""
        policy = PolicyConfig(max_findings=5)
        findings = [{"severity": "low", "rule": "TEST"}] * 6
        code, messages = get_exit_code_from_policy(findings, policy)

        assert code == 2
        assert "max_findings" in messages[0]

    def test_multiple_violations(self):
        """Test multiple policy violations."""
        policy = PolicyConfig(
            fail_on_critical=True,
            warn_at=5,
        )
        findings = [
            {"severity": "critical", "rule": "TEST1"},
            {"severity": "low", "rule": "TEST2"},
            {"severity": "low", "rule": "TEST3"},
            {"severity": "low", "rule": "TEST4"},
            {"severity": "low", "rule": "TEST5"},
            {"severity": "low", "rule": "TEST6"},
        ]
        code, messages = get_exit_code_from_policy(findings, policy)

        assert code == 2  # Critical takes precedence
        assert len(messages) >= 2  # Both critical and warn_at
