"""Policy enforcement for quality gates and inline suppressions."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PolicyConfig:
    fail_on_error: bool = True
    fail_on_risky: bool = True
    max_warnings: int | None = None
    max_errors: int = 0
    max_complexity: int = 15
    max_function_length: int = 50
    suppression_enabled: bool = True

    @classmethod
    def from_file(cls, path: Path) -> "PolicyConfig":
        if not path or not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def to_dict(self) -> dict:
        return {
            "fail_on_error": self.fail_on_error,
            "fail_on_risky": self.fail_on_risky,
            "max_warnings": self.max_warnings,
            "max_errors": self.max_errors,
            "max_complexity": self.max_complexity,
            "max_function_length": self.max_function_length,
            "suppression_enabled": self.suppression_enabled,
        }


class PolicyEnforcer:
    """Simple severity gate with risky-construct hard fail."""

    def __init__(self, config: PolicyConfig):
        self.config = config

    def _severity_to_string(self, severity) -> str:
        """Convert numeric severity to string for classification"""
        if isinstance(severity, str):
            return severity.lower()

        # Numeric severity mapping: 0.1=info, 0.4=warning, 0.7=error, 0.9=critical
        if severity >= 0.9:
            return "critical"
        elif severity >= 0.7:
            return "error"
        elif severity >= 0.4:
            return "warning"
        else:
            return "info"

    def check_violations(self, analysis_results: dict) -> tuple[bool, list[str]]:
        violations: list[str] = []
        errors = 0
        warnings = 0
        risky = 0

        for issue in analysis_results.get("issues", []):
            sev_raw = issue.get("severity", "info")
            sev = self._severity_to_string(sev_raw)
            rule = issue.get("rule", "")
            if "risky" in rule:
                risky += 1
            if sev in ("error", "critical"):
                errors += 1
            elif sev == "warning":
                warnings += 1

        if self.config.fail_on_risky and risky > 0:
            violations.append(f"Found {risky} risky construct(s)")
        if self.config.fail_on_error and errors > self.config.max_errors:
            violations.append(f"Errors ({errors}) exceed limit ({self.config.max_errors})")
        if self.config.max_warnings is not None and warnings > self.config.max_warnings:
            violations.append(f"Warnings ({warnings}) exceed limit ({self.config.max_warnings})")

        return (len(violations) == 0, violations)

    def filter_suppressed(self, issues: list[dict], source_lines: list[str]) -> list[dict]:
        if not self.config.suppression_enabled:
            return issues
        filtered: list[dict] = []
        for issue in issues:
            ln = issue.get("line", 0)
            rule = issue.get("rule", "")
            if 1 <= ln <= len(source_lines):
                line = source_lines[ln - 1]
                if f"# acha: disable={rule}" in line or "# acha: disable-all" in line:
                    continue
            filtered.append(issue)
        return filtered
