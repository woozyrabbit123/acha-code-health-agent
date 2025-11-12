"""Policy engine for quality gates and thresholds."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

# Default weights for R* calculation
DEFAULT_ALPHA = 0.7  # Weight for severity
DEFAULT_BETA = 0.3  # Weight for complexity

# Decision thresholds
AUTO_THRESHOLD = 0.70  # Auto-apply if R* >= 0.70
SUGGEST_THRESHOLD = 0.50  # Suggest if R* >= 0.50


class Decision(str, Enum):
    """Refactoring decision based on R* score."""

    AUTO = "auto"  # Auto-apply refactoring
    SUGGEST = "suggest"  # Suggest to user
    SKIP = "skip"  # Skip refactoring


@dataclass(slots=True)
class PolicyEngine:
    """
    Multi-language policy enforcement engine.

    Attributes:
        max_findings: Maximum allowed findings (0 = unlimited)
        fail_on_critical: Fail if any critical severity findings
        alpha: Weight for severity in R* calculation
        beta: Weight for complexity in R* calculation
        auto_threshold: R* threshold for auto-apply
        suggest_threshold: R* threshold for suggest
    """

    max_findings: int = 0
    fail_on_critical: bool = True
    alpha: float = DEFAULT_ALPHA
    beta: float = DEFAULT_BETA
    auto_threshold: float = AUTO_THRESHOLD
    suggest_threshold: float = SUGGEST_THRESHOLD

    def evaluate(self, findings: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        """
        Evaluate findings against policy.

        Args:
            findings: List of UIR findings (as dicts)

        Returns:
            Tuple of (passed, violation_messages)
        """
        violations = []

        # Check max findings
        if self.max_findings > 0 and len(findings) > self.max_findings:
            violations.append(
                f"Exceeded max findings: {len(findings)} > {self.max_findings}"
            )

        # Check for critical findings
        if self.fail_on_critical:
            critical_count = sum(
                1 for f in findings if f.get("severity") == "critical"
            )
            if critical_count > 0:
                violations.append(f"Found {critical_count} critical severity findings")

        return (len(violations) == 0, violations)


def rstar(
    severity: float, complexity: float, alpha: float = DEFAULT_ALPHA, beta: float = DEFAULT_BETA
) -> float:
    """
    Calculate R* (risk/refactoring score) for a finding.

    R* = α × severity + β × complexity

    Args:
        severity: Severity score (0.0 to 1.0)
        complexity: Complexity score (0.0 to 1.0)
        alpha: Weight for severity (default: 0.7)
        beta: Weight for complexity (default: 0.3)

    Returns:
        R* score (0.0 to 1.0)

    Examples:
        >>> rstar(0.9, 0.8)  # High severity, high complexity
        0.87
        >>> rstar(0.5, 0.3)  # Medium severity, low complexity
        0.44
        >>> rstar(1.0, 1.0)  # Maximum values
        1.0
    """
    # Validate inputs
    severity = max(0.0, min(1.0, severity))
    complexity = max(0.0, min(1.0, complexity))

    # Calculate weighted score
    score = alpha * severity + beta * complexity

    # Ensure result is in [0.0, 1.0] range
    return max(0.0, min(1.0, score))


def decision(
    rstar_value: float,
    auto_threshold: float = AUTO_THRESHOLD,
    suggest_threshold: float = SUGGEST_THRESHOLD,
) -> Decision:
    """
    Make refactoring decision based on R* score.

    Thresholds:
    - R* >= auto_threshold (0.70): AUTO
    - R* >= suggest_threshold (0.50): SUGGEST
    - R* < suggest_threshold: SKIP

    Args:
        rstar_value: R* score (0.0 to 1.0)
        auto_threshold: Threshold for auto-apply (default: 0.70)
        suggest_threshold: Threshold for suggest (default: 0.50)

    Returns:
        Decision enum (AUTO, SUGGEST, or SKIP)

    Examples:
        >>> decision(0.85)
        <Decision.AUTO: 'auto'>
        >>> decision(0.60)
        <Decision.SUGGEST: 'suggest'>
        >>> decision(0.40)
        <Decision.SKIP: 'skip'>
    """
    if rstar_value >= auto_threshold:
        return Decision.AUTO
    elif rstar_value >= suggest_threshold:
        return Decision.SUGGEST
    else:
        return Decision.SKIP


def enforce_policy(findings: list, policy_config: dict) -> tuple[bool, list[str]]:
    """
    Enforce policy on findings.

    Args:
        findings: List of UIR findings (dicts or UnifiedIssue objects)
        policy_config: Policy configuration dict

    Returns:
        Tuple of (passed, violation_messages)

    Examples:
        >>> findings = [{"severity": "critical", "rule": "test"}]
        >>> enforce_policy(findings, {"fail_on_critical": True})
        (False, ['Found 1 critical severity findings'])
    """
    # Convert findings to dicts if needed
    findings_dicts = []
    for f in findings:
        if hasattr(f, "to_dict"):
            findings_dicts.append(f.to_dict())
        else:
            findings_dicts.append(f)

    # Create policy engine from config
    engine = PolicyEngine(
        max_findings=policy_config.get("max_findings", 0),
        fail_on_critical=policy_config.get("fail_on_critical", True),
        alpha=policy_config.get("alpha", DEFAULT_ALPHA),
        beta=policy_config.get("beta", DEFAULT_BETA),
        auto_threshold=policy_config.get("auto_threshold", AUTO_THRESHOLD),
        suggest_threshold=policy_config.get("suggest_threshold", SUGGEST_THRESHOLD),
    )

    return engine.evaluate(findings_dicts)
