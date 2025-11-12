"""Tests for GitHub Actions infrastructure detection."""

import pytest
from pathlib import Path

from ace.skills.github_actions import (
    RULE_MISSING_PERMISSIONS,
    RULE_UNPINNED_ACTION,
    RULE_WRITE_ALL,
    analyze_github_workflow,
    is_github_workflow,
)


class TestIsGitHubWorkflow:
    """Tests for GHA workflow detection."""

    def test_workflow_file(self):
        """Test standard workflow file."""
        assert is_github_workflow(Path(".github/workflows/ci.yml"))

    def test_workflow_yaml(self):
        """Test .yaml extension."""
        assert is_github_workflow(Path(".github/workflows/test.yaml"))

    def test_non_workflow(self):
        """Test non-workflow file."""
        assert not is_github_workflow(Path("config.yml"))


class TestGHAAnalysis:
    """Tests for GHA workflow analysis."""

    def test_unpinned_action_tag(self):
        """Test detection of unpinned action (tag ref)."""
        content = """
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
"""
        findings = analyze_github_workflow(".github/workflows/test.yml", content)

        unpinned = [f for f in findings if f.rule == RULE_UNPINNED_ACTION]
        assert len(unpinned) >= 1

    def test_unpinned_action_branch(self):
        """Test detection of unpinned action (branch ref)."""
        content = """
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
"""
        findings = analyze_github_workflow(".github/workflows/test.yml", content)

        unpinned = [f for f in findings if f.rule == RULE_UNPINNED_ACTION]
        assert len(unpinned) >= 1

    def test_pinned_action_sha(self):
        """Test that SHA-pinned actions don't trigger."""
        content = """
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
"""
        findings = analyze_github_workflow(".github/workflows/test.yml", content)

        unpinned = [f for f in findings if f.rule == RULE_UNPINNED_ACTION]
        assert len(unpinned) == 0

    def test_write_all_permissions(self):
        """Test detection of write-all permissions."""
        content = """
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    permissions: write-all
    steps:
      - run: echo hello
"""
        findings = analyze_github_workflow(".github/workflows/test.yml", content)

        write_all = [f for f in findings if f.rule == RULE_WRITE_ALL]
        assert len(write_all) >= 1

    def test_missing_permissions(self):
        """Test detection of missing permissions."""
        content = """
name: Test
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""
        findings = analyze_github_workflow(".github/workflows/test.yml", content)

        missing = [f for f in findings if f.rule == RULE_MISSING_PERMISSIONS]
        assert len(missing) >= 1

    def test_explicit_permissions(self):
        """Test that explicit permissions prevent finding."""
        content = """
name: Test
on: push
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""
        findings = analyze_github_workflow(".github/workflows/test.yml", content)

        missing = [f for f in findings if f.rule == RULE_MISSING_PERMISSIONS]
        assert len(missing) == 0
