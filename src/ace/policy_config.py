"""Policy configuration loader - TOML-based policy management."""

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ace.policy import DEFAULT_ALPHA, DEFAULT_BETA, AUTO_THRESHOLD, SUGGEST_THRESHOLD

# Python 3.11+ has tomllib built-in, earlier versions need tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore


@dataclass
class PolicyConfig:
    """
    Policy configuration loaded from TOML.

    Attributes:
        version: Policy version
        description: Policy description
        alpha: R* severity weight
        beta: R* complexity weight
        gamma: R* pack cohesion weight
        auto_threshold: Auto-apply threshold
        suggest_threshold: Suggest threshold
        max_findings: Maximum findings limit
        fail_on_critical: Fail on critical findings
        warn_at: Warning threshold
        fail_at: Failure threshold
        modes: Rule mode mapping (rule_id -> "auto-fix" | "detect-only")
        risk_classes: Risk class mapping (class -> list[rule_id])
        suppressions_paths: Global suppression paths
        suppressions_rules: Rule-specific suppression paths
        packs_enabled: Enable macro-fix packs
        packs_min_findings: Minimum findings for pack
        packs_prefer: Prefer packs over individual plans
        raw_config: Raw TOML config dict
    """

    version: str = "0.7.0"
    description: str = "ACE policy configuration"

    # Scoring - defaults imported from policy.py to avoid duplication
    alpha: float = DEFAULT_ALPHA  # 0.7
    beta: float = DEFAULT_BETA  # 0.3
    gamma: float = 0.2
    auto_threshold: float = AUTO_THRESHOLD  # 0.70
    suggest_threshold: float = SUGGEST_THRESHOLD  # 0.50

    # Limits
    max_findings: int = 0
    fail_on_critical: bool = True
    warn_at: int = 50
    fail_at: int = 100

    # Modes and classifications
    modes: dict[str, str] = field(default_factory=dict)
    risk_classes: dict[str, list[str]] = field(default_factory=dict)

    # Suppressions
    suppressions_paths: list[str] = field(default_factory=list)
    suppressions_rules: dict[str, list[str]] = field(default_factory=dict)

    # Packs
    packs_enabled: bool = True
    packs_min_findings: int = 2
    packs_prefer: bool = True

    # Raw config for hashing
    raw_config: dict[str, Any] = field(default_factory=dict)

    def get_mode(self, rule_id: str) -> str:
        """
        Get mode for a rule.

        Args:
            rule_id: Rule identifier

        Returns:
            Mode string ("auto-fix" or "detect-only")
        """
        return self.modes.get(rule_id, "auto-fix")

    def is_auto_fix(self, rule_id: str) -> bool:
        """
        Check if rule should be auto-fixed.

        Args:
            rule_id: Rule identifier

        Returns:
            True if auto-fix, False if detect-only
        """
        return self.get_mode(rule_id) == "auto-fix"

    def get_risk_class(self, rule_id: str) -> str | None:
        """
        Get risk class for a rule.

        Args:
            rule_id: Rule identifier

        Returns:
            Risk class name or None if not classified
        """
        for risk_class, rules in self.risk_classes.items():
            if rule_id in rules:
                return risk_class
        return None

    def is_suppressed(self, file_path: str, rule_id: str) -> bool:
        """
        Check if a file/rule combination is suppressed.

        Args:
            file_path: File path to check
            rule_id: Rule identifier

        Returns:
            True if suppressed, False otherwise
        """
        from pathlib import Path
        from fnmatch import fnmatch

        path = Path(file_path)

        # Check global suppressions
        for pattern in self.suppressions_paths:
            if fnmatch(str(path), pattern) or fnmatch(path.name, pattern):
                return True

        # Check rule-specific suppressions
        if rule_id in self.suppressions_rules:
            for pattern in self.suppressions_rules[rule_id]:
                if fnmatch(str(path), pattern) or fnmatch(path.name, pattern):
                    return True

        return False


def load_policy_config(policy_path: Path | str | None = None) -> PolicyConfig:
    """
    Load policy configuration from TOML file.

    Args:
        policy_path: Path to policy.toml (or None to use default)

    Returns:
        PolicyConfig object

    Raises:
        FileNotFoundError: If policy file doesn't exist
        ValueError: If TOML is invalid or missing required fields
    """
    if tomllib is None:
        raise ImportError(
            "TOML support requires Python 3.11+ or 'tomli' package. "
            "Install with: pip install tomli"
        )

    # Default to policy.toml in current directory
    if policy_path is None:
        policy_path = Path("policy.toml")
    else:
        policy_path = Path(policy_path)

    if not policy_path.exists():
        # Return default config if no policy file
        return PolicyConfig()

    # Load TOML
    try:
        with open(policy_path, "rb") as f:
            config = tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse {policy_path}: {e}") from e

    # Extract configuration
    meta = config.get("meta", {})
    scoring = config.get("scoring", {})
    limits = config.get("limits", {})
    modes = config.get("modes", {})
    risk_classes = config.get("risk_classes", {})
    suppressions = config.get("suppressions", {})
    packs = config.get("packs", {})

    # Build PolicyConfig
    policy = PolicyConfig(
        version=meta.get("version", "0.7.0"),
        description=meta.get("description", "ACE policy configuration"),
        # Scoring - use shared constants from policy.py
        alpha=scoring.get("alpha", DEFAULT_ALPHA),
        beta=scoring.get("beta", DEFAULT_BETA),
        gamma=scoring.get("gamma", 0.2),
        auto_threshold=scoring.get("auto_threshold", AUTO_THRESHOLD),
        suggest_threshold=scoring.get("suggest_threshold", SUGGEST_THRESHOLD),
        # Limits
        max_findings=limits.get("max_findings", 0),
        fail_on_critical=limits.get("fail_on_critical", True),
        warn_at=limits.get("warn_at", 50),
        fail_at=limits.get("fail_at", 100),
        # Modes and classifications
        modes=modes,
        risk_classes=risk_classes,
        # Suppressions
        suppressions_paths=suppressions.get("paths", []),
        suppressions_rules=suppressions.get("rules", {}),
        # Packs
        packs_enabled=packs.get("enabled", True),
        packs_min_findings=packs.get("min_findings", 2),
        packs_prefer=packs.get("prefer_packs", True),
        # Store raw config for hashing
        raw_config=config,
    )

    # Validate
    validate_policy_config(policy)

    return policy


def validate_policy_config(policy: PolicyConfig) -> None:
    """
    Validate policy configuration.

    Args:
        policy: PolicyConfig to validate

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate weights
    if not 0.0 <= policy.alpha <= 1.0:
        raise ValueError(f"alpha must be in [0.0, 1.0], got {policy.alpha}")
    if not 0.0 <= policy.beta <= 1.0:
        raise ValueError(f"beta must be in [0.0, 1.0], got {policy.beta}")
    if not 0.0 <= policy.gamma <= 1.0:
        raise ValueError(f"gamma must be in [0.0, 1.0], got {policy.gamma}")

    # Validate thresholds
    if not 0.0 <= policy.auto_threshold <= 1.0:
        raise ValueError(f"auto_threshold must be in [0.0, 1.0], got {policy.auto_threshold}")
    if not 0.0 <= policy.suggest_threshold <= 1.0:
        raise ValueError(f"suggest_threshold must be in [0.0, 1.0], got {policy.suggest_threshold}")
    if policy.auto_threshold < policy.suggest_threshold:
        raise ValueError(
            f"auto_threshold ({policy.auto_threshold}) must be >= suggest_threshold ({policy.suggest_threshold})"
        )

    # Validate limits
    if policy.max_findings < 0:
        raise ValueError(f"max_findings must be >= 0, got {policy.max_findings}")
    if policy.warn_at < 0:
        raise ValueError(f"warn_at must be >= 0, got {policy.warn_at}")
    if policy.fail_at < 0:
        raise ValueError(f"fail_at must be >= 0, got {policy.fail_at}")

    # Validate modes
    for rule_id, mode in policy.modes.items():
        if mode not in ("auto-fix", "detect-only"):
            raise ValueError(
                f"Invalid mode for {rule_id}: {mode}. Must be 'auto-fix' or 'detect-only'"
            )

    # Validate packs
    if policy.packs_min_findings < 1:
        raise ValueError(f"packs_min_findings must be >= 1, got {policy.packs_min_findings}")


def policy_hash(policy: PolicyConfig) -> str:
    """
    Compute SHA256 hash of policy configuration.

    Uses normalized TOML representation for stability.

    Args:
        policy: PolicyConfig object

    Returns:
        SHA256 hash (hex string, first 16 chars)

    Examples:
        >>> policy = PolicyConfig()
        >>> hash1 = policy_hash(policy)
        >>> hash2 = policy_hash(policy)
        >>> hash1 == hash2
        True
    """
    # Serialize policy to normalized form
    normalized = _normalize_policy_dict(policy.raw_config)
    hash_bytes = hashlib.sha256(normalized.encode("utf-8")).digest()
    return hash_bytes.hex()[:16]


def _normalize_policy_dict(d: dict[str, Any], indent: int = 0) -> str:
    """
    Normalize policy dict to stable string representation.

    Args:
        d: Dictionary to normalize
        indent: Current indentation level

    Returns:
        Normalized string representation
    """
    lines = []
    for key in sorted(d.keys()):
        value = d[key]
        prefix = "  " * indent

        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_normalize_policy_dict(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: {sorted(str(v) for v in value)}")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return "\n".join(lines)


def aggregate_findings_by_risk_class(
    findings: list[dict[str, Any]],
    policy: PolicyConfig,
) -> dict[str, int]:
    """
    Aggregate findings by risk class.

    Args:
        findings: List of UIR finding dicts
        policy: PolicyConfig object

    Returns:
        Dictionary mapping risk class to count

    Examples:
        >>> findings = [
        ...     {"rule": "PY-S101-UNSAFE-HTTP", "severity": "high"},
        ...     {"rule": "PY-E201-BROAD-EXCEPT", "severity": "medium"},
        ... ]
        >>> policy = PolicyConfig()
        >>> policy.risk_classes = {
        ...     "security": ["PY-S101-UNSAFE-HTTP"],
        ...     "reliability": ["PY-E201-BROAD-EXCEPT"],
        ... }
        >>> counts = aggregate_findings_by_risk_class(findings, policy)
        >>> counts["security"]
        1
        >>> counts["reliability"]
        1
    """
    counts: dict[str, int] = {}

    for finding in findings:
        rule_id = finding.get("rule", "")
        risk_class = policy.get_risk_class(rule_id)

        if risk_class:
            counts[risk_class] = counts.get(risk_class, 0) + 1
        else:
            counts["uncategorized"] = counts.get("uncategorized", 0) + 1

    return counts


def get_exit_code_from_policy(
    findings: list[dict[str, Any]],
    policy: PolicyConfig,
) -> tuple[int, list[str]]:
    """
    Get exit code based on policy enforcement.

    Args:
        findings: List of UIR finding dicts
        policy: PolicyConfig object

    Returns:
        Tuple of (exit_code, messages)
        - 0: Success
        - 1: Warning threshold exceeded
        - 2: Failure threshold exceeded or critical findings

    Examples:
        >>> findings = [{"severity": "critical", "rule": "TEST"}]
        >>> policy = PolicyConfig(fail_on_critical=True)
        >>> code, msgs = get_exit_code_from_policy(findings, policy)
        >>> code
        2
    """
    messages = []
    exit_code = 0

    # Check critical findings
    if policy.fail_on_critical:
        critical_count = sum(1 for f in findings if f.get("severity") == "critical")
        if critical_count > 0:
            messages.append(f"Found {critical_count} critical severity findings")
            exit_code = 2

    # Check thresholds
    finding_count = len(findings)

    if policy.fail_at > 0 and finding_count >= policy.fail_at:
        messages.append(f"Finding count {finding_count} exceeds fail_at threshold {policy.fail_at}")
        exit_code = max(exit_code, 2)
    elif policy.warn_at > 0 and finding_count >= policy.warn_at:
        messages.append(f"Finding count {finding_count} exceeds warn_at threshold {policy.warn_at}")
        exit_code = max(exit_code, 1)

    # Check max_findings
    if policy.max_findings > 0 and finding_count > policy.max_findings:
        messages.append(f"Finding count {finding_count} exceeds max_findings {policy.max_findings}")
        exit_code = max(exit_code, 2)

    return exit_code, messages
