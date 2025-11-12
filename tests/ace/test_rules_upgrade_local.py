"""Test local rules version management."""

import json
import tempfile
from pathlib import Path

from ace.rules_local import bump_rules_version, get_rules_version, init_rules


def test_init_rules():
    """Test initializing rules.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        rules_path = tmpdir / ".ace" / "rules.json"

        # Initialize rules
        init_rules(rules_path)

        # Should create the file
        assert rules_path.exists()

        # Should have version
        version = get_rules_version(rules_path)
        assert version != "unknown"
        assert len(version) > 0


def test_bump_rules_version_creates_deterministic_file():
    """Test that bump_rules_version creates deterministic output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        rules_path = tmpdir / ".ace" / "rules.json"

        # Bump version twice
        bump_rules_version(rules_path)
        content1 = rules_path.read_text(encoding="utf-8")

        # Remove file and bump again
        rules_path.unlink()
        bump_rules_version(rules_path)
        content2 = rules_path.read_text(encoding="utf-8")

        # Should produce identical output (deterministic)
        assert content1 == content2


def test_bump_rules_version_sorted_catalog():
    """Test that rules catalog is sorted by ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        rules_path = tmpdir / ".ace" / "rules.json"

        # Bump version
        bump_rules_version(rules_path)

        # Load rules
        with open(rules_path, "r", encoding="utf-8") as f:
            rules_doc = json.load(f)

        # Check that rules are sorted by ID
        rule_ids = [rule["id"] for rule in rules_doc["rules"]]
        assert rule_ids == sorted(rule_ids)


def test_get_rules_version_unknown():
    """Test get_rules_version with missing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        rules_path = tmpdir / ".ace" / "rules.json"

        # Should return "unknown" for missing file
        version = get_rules_version(rules_path)
        assert version == "unknown"


def test_bump_rules_version_has_content_hash():
    """Test that bumped rules include content hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        rules_path = tmpdir / ".ace" / "rules.json"

        # Bump version
        bump_rules_version(rules_path)

        # Load rules
        with open(rules_path, "r", encoding="utf-8") as f:
            rules_doc = json.load(f)

        # Should have content_hash field
        assert "content_hash" in rules_doc
        assert len(rules_doc["content_hash"]) > 0


def test_bump_rules_version_stable_across_runs():
    """Test that multiple bumps produce stable IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        rules_path = tmpdir / ".ace" / "rules.json"

        # Bump version
        bump_rules_version(rules_path)
        version1 = get_rules_version(rules_path)

        # Bump again (should be idempotent)
        bump_rules_version(rules_path)
        version2 = get_rules_version(rules_path)

        # Version should be the same (no auto-increment)
        assert version1 == version2
