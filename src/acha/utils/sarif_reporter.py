"""SARIF 2.1.0 report generator for ACHA findings"""

import json
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SARIFReporter:
    """Generate SARIF 2.1.0 compliant reports for CI/CD integration"""

    # SARIF severity level mapping
    SEVERITY_LEVELS = {
        "critical": "error",
        "error": "error",
        "warning": "warning",
        "info": "note",
        0.9: "error",  # numeric critical
        0.7: "error",  # numeric error
        0.4: "warning",  # numeric warning
        0.1: "note",  # numeric info
    }

    # Rule metadata for ACHA analyzers
    RULE_DEFINITIONS = {
        "dup_immutable_const": {
            "id": "ACHA001",
            "name": "DuplicateImmutableConstant",
            "shortDescription": {"text": "Duplicate immutable constant detected"},
            "fullDescription": {
                "text": "Multiple assignments of the same immutable constant value. Consider extracting to a named constant."
            },
            "help": {
                "text": "Extract duplicate constants to improve maintainability and reduce magic numbers."
            },
            "defaultConfiguration": {"level": "warning"},
        },
        "risky_construct": {
            "id": "ACHA002",
            "name": "RiskyConstruct",
            "shortDescription": {"text": "Risky code construct detected"},
            "fullDescription": {
                "text": "Code uses potentially dangerous constructs like eval(), exec(), or __import__()."
            },
            "help": {
                "text": "Avoid using dangerous functions. Use safer alternatives or validate inputs carefully."
            },
            "defaultConfiguration": {"level": "error"},
        },
        "unused_import": {
            "id": "ACHA003",
            "name": "UnusedImport",
            "shortDescription": {"text": "Unused import statement"},
            "fullDescription": {"text": "Import statement is not used anywhere in the file."},
            "help": {"text": "Remove unused imports to keep code clean and reduce dependencies."},
            "defaultConfiguration": {"level": "warning"},
        },
        "magic_number": {
            "id": "ACHA004",
            "name": "MagicNumber",
            "shortDescription": {"text": "Magic number without explanation"},
            "fullDescription": {
                "text": "Numeric constant used without explanation. Consider extracting to a named constant."
            },
            "help": {
                "text": "Replace magic numbers with named constants to improve code readability."
            },
            "defaultConfiguration": {"level": "note"},
        },
        "missing_docstring": {
            "id": "ACHA005",
            "name": "MissingDocstring",
            "shortDescription": {"text": "Function missing docstring"},
            "fullDescription": {"text": "Public function lacks documentation string."},
            "help": {
                "text": "Add docstrings to document function purpose, parameters, and return values."
            },
            "defaultConfiguration": {"level": "note"},
        },
        "high_complexity": {
            "id": "ACHA006",
            "name": "HighComplexity",
            "shortDescription": {"text": "High cyclomatic complexity"},
            "fullDescription": {
                "text": "Function has high cyclomatic complexity, making it difficult to test and maintain."
            },
            "help": {"text": "Refactor complex functions into smaller, more focused functions."},
            "defaultConfiguration": {"level": "warning"},
        },
        "broad_exception": {
            "id": "ACHA007",
            "name": "BroadExceptionCatch",
            "shortDescription": {"text": "Broad exception handler"},
            "fullDescription": {
                "text": "Exception handler catches broad exception types (Exception, BaseException)."
            },
            "help": {"text": "Catch specific exceptions to handle errors appropriately."},
            "defaultConfiguration": {"level": "warning"},
        },
        "broad_subprocess_shell": {
            "id": "ACHA008",
            "name": "SubprocessShellTrue",
            "shortDescription": {"text": "Subprocess called with shell=True"},
            "fullDescription": {
                "text": "Using subprocess with shell=True can be a security risk if untrusted input is used."
            },
            "help": {
                "text": "Avoid shell=True or carefully validate all inputs to prevent shell injection."
            },
            "defaultConfiguration": {"level": "error"},
        },
    }

    def __init__(self, tool_name: str = "ACHA", version: str = "0.3.0"):
        """
        Initialize SARIF reporter.

        Args:
            tool_name: Name of the analysis tool
            version: Version of the analysis tool
        """
        self.tool_name = tool_name
        self.version = version

    def generate(self, findings: list[dict], base_path: Path) -> dict:
        """
        Convert ACHA findings to SARIF 2.1.0 format.

        Args:
            findings: List of ACHA findings
            base_path: Base path for relative file paths

        Returns:
            SARIF document as dictionary
        """
        base_path = Path(base_path).resolve()

        # Build SARIF document
        sarif_doc = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": self.tool_name,
                            "version": self.version,
                            "informationUri": "https://github.com/woozyrabbit123/acha-code-health-agent",
                            "rules": self._build_rules(findings),
                        }
                    },
                    "results": self._build_results(findings, base_path),
                    "columnKind": "utf16CodeUnits",
                    "invocations": [
                        {"executionSuccessful": True, "endTimeUtc": datetime.now(UTC).isoformat()}
                    ],
                }
            ],
        }

        return sarif_doc

    def _build_rules(self, findings: list[dict]) -> list[dict]:
        """Build rules array from findings"""
        # Collect unique rule types
        rule_types = set()
        for finding in findings:
            rule_type = finding.get("finding") or finding.get("rule", "unknown")
            rule_types.add(rule_type)

        # Build rule definitions
        rules = []
        for rule_type in sorted(rule_types):
            if rule_type in self.RULE_DEFINITIONS:
                rule_def = self.RULE_DEFINITIONS[rule_type].copy()
                rules.append(rule_def)
            else:
                # Generic rule for unknown types
                rules.append(
                    {
                        "id": f"ACHA{len(rules)+100:03d}",
                        "name": rule_type.replace("_", " ").title().replace(" ", ""),
                        "shortDescription": {"text": f"{rule_type} detected"},
                        "defaultConfiguration": {"level": "warning"},
                    }
                )

        return rules

    def _build_results(self, findings: list[dict], base_path: Path) -> list[dict]:
        """Build results array from findings"""
        results = []

        for finding in findings:
            result = self._finding_to_result(finding, base_path)
            if result:
                results.append(result)

        return results

    def _finding_to_result(self, finding: dict, base_path: Path) -> dict | None:
        """Convert a single finding to a SARIF result"""
        rule_type = finding.get("finding") or finding.get("rule", "unknown")
        rule_id = self._get_rule_id(rule_type)

        # Get file location
        file_path = finding.get("file", "")
        if not file_path:
            return None

        # Make path relative to base_path
        try:
            abs_path = (base_path / file_path).resolve()
            rel_path = abs_path.relative_to(base_path)
            uri = rel_path.as_posix()
        except (ValueError, OSError):
            uri = file_path

        # Get line information
        start_line = finding.get("line") or finding.get("start_line", 1)
        end_line = finding.get("end_line", start_line)

        # Build location
        location = {
            "physicalLocation": {
                "artifactLocation": {"uri": uri, "uriBaseId": "%SRCROOT%"},
                "region": {"startLine": start_line, "endLine": end_line},
            }
        }

        # Get severity
        severity = finding.get("severity", "warning")
        level = self._map_severity(severity)

        # Build message
        message_text = finding.get("rationale") or finding.get("message", "")
        if not message_text:
            message_text = f"{rule_type} detected"

        result = {
            "ruleId": rule_id,
            "level": level,
            "message": {"text": message_text},
            "locations": [location],
        }

        # Add optional fields if available
        if "id" in finding:
            result["properties"] = {"finding_id": finding["id"]}

        return result

    def _get_rule_id(self, rule_type: str) -> str:
        """Get deterministic SARIF rule ID for a rule type"""
        if rule_type in self.RULE_DEFINITIONS:
            return self.RULE_DEFINITIONS[rule_type]["id"]
        # Use CRC32 for deterministic hash across runs
        rule_hash = zlib.crc32(rule_type.encode("utf-8")) % 1000
        return f"ACHA{rule_hash:03d}"

    def _map_severity(self, severity: Any) -> str:
        """Map ACHA severity to SARIF level"""
        # Handle string severity
        if isinstance(severity, str):
            severity_lower = severity.lower()
            return self.SEVERITY_LEVELS.get(severity_lower, "warning")

        # Handle numeric severity
        if isinstance(severity, (int, float)):
            return self.SEVERITY_LEVELS.get(severity, "warning")

        return "warning"

    def write(self, sarif_data: dict, output_path: Path):
        """
        Write SARIF data to file.

        Args:
            sarif_data: SARIF document dictionary
            output_path: Output file path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sarif_data, f, indent=2, ensure_ascii=False)

    def generate_and_write(self, findings: list[dict], base_path: Path, output_path: Path):
        """
        Generate SARIF report and write to file.

        Args:
            findings: List of ACHA findings
            base_path: Base path for relative file paths
            output_path: Output file path
        """
        sarif_data = self.generate(findings, base_path)
        self.write(sarif_data, output_path)
