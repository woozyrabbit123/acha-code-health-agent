"""Regression tests for SARIF determinism issues"""
from pathlib import Path
import tempfile
from utils.sarif_reporter import SARIFReporter


def test_sarif_rule_ids_deterministic():
    """Test that unknown rule types generate deterministic IDs across multiple calls"""
    reporter = SARIFReporter()

    # Test with unknown rule type
    unknown_rule = "custom_security_rule"

    # Generate ID multiple times
    id1 = reporter._get_rule_id(unknown_rule)
    id2 = reporter._get_rule_id(unknown_rule)
    id3 = reporter._get_rule_id(unknown_rule)

    # All IDs should be identical
    assert id1 == id2, f"Rule IDs must be deterministic: {id1} != {id2}"
    assert id2 == id3, f"Rule IDs must be deterministic: {id2} != {id3}"
    assert id1 == id3, f"Rule IDs must be deterministic: {id1} != {id3}"

    # IDs should follow ACHA convention
    assert id1.startswith("ACHA"), f"Rule ID should start with ACHA, got {id1}"

    # ID should be in correct format (ACHA followed by 3 digits)
    assert len(id1) == 7, f"Rule ID should be 7 characters (ACHA + 3 digits), got {id1}"
    assert id1[4:].isdigit(), f"Last 3 characters should be digits, got {id1}"


def test_sarif_multiple_unknown_rules_deterministic():
    """Test that multiple unknown rule types each get consistent IDs"""
    reporter = SARIFReporter()

    rules = [
        "custom_rule_1",
        "custom_rule_2",
        "security_check_x",
        "performance_issue_y"
    ]

    # Generate IDs for each rule multiple times
    for rule in rules:
        id1 = reporter._get_rule_id(rule)
        id2 = reporter._get_rule_id(rule)

        assert id1 == id2, f"Rule {rule} should have deterministic ID: {id1} != {id2}"
        assert id1.startswith("ACHA"), f"Rule ID should start with ACHA"


def test_sarif_known_rules_unchanged():
    """Test that known rule types still return their defined IDs"""
    reporter = SARIFReporter()

    # Test all known rule types
    known_rules = {
        "dup_immutable_const": "ACHA001",
        "risky_construct": "ACHA002",
        "unused_import": "ACHA003",
        "magic_number": "ACHA004",
        "missing_docstring": "ACHA005",
        "high_complexity": "ACHA006",
        "broad_exception": "ACHA007",
        "broad_subprocess_shell": "ACHA008"
    }

    for rule_type, expected_id in known_rules.items():
        actual_id = reporter._get_rule_id(rule_type)
        assert actual_id == expected_id, \
            f"Known rule {rule_type} should return {expected_id}, got {actual_id}"


def test_sarif_full_report_deterministic(tmp_path):
    """Test that full SARIF reports are deterministic with unknown rules"""
    findings = [
        {
            "finding": "custom_unknown_rule",
            "file": "test.py",
            "line": 1,
            "severity": 0.5
        }
    ]

    reporter1 = SARIFReporter()
    reporter2 = SARIFReporter()

    # Generate SARIF reports with same data
    sarif1 = reporter1.generate(findings, tmp_path)
    sarif2 = reporter2.generate(findings, tmp_path)

    # Extract rule IDs from both reports
    rules1 = sarif1["runs"][0]["tool"]["driver"]["rules"]
    rules2 = sarif2["runs"][0]["tool"]["driver"]["rules"]

    # Rule IDs should be identical
    assert len(rules1) == len(rules2), "Should have same number of rules"

    for r1, r2 in zip(rules1, rules2):
        assert r1["id"] == r2["id"], \
            f"Rule IDs should be deterministic: {r1['id']} != {r2['id']}"


def test_sarif_crc32_consistency():
    """Test that CRC32 hash is consistent for same input"""
    import zlib

    test_strings = [
        "test_rule_1",
        "another_rule",
        "security_check",
        "performance_issue"
    ]

    for test_str in test_strings:
        # Calculate CRC32 multiple times
        hash1 = zlib.crc32(test_str.encode("utf-8")) % 1000
        hash2 = zlib.crc32(test_str.encode("utf-8")) % 1000
        hash3 = zlib.crc32(test_str.encode("utf-8")) % 1000

        assert hash1 == hash2 == hash3, \
            f"CRC32 should be deterministic for {test_str}"
