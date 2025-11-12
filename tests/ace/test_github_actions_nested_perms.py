"""Test GitHub Actions nested permissions detection."""

import pytest
from ace.skills.github_actions import analyze_github_workflow


def test_nested_write_all_detection():
    """Test detection of write-all in nested permissions dict."""
    workflow = """
name: Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: write-all
    steps:
      - uses: actions/checkout@v3
"""
    findings = analyze_github_workflow(".github/workflows/test.yml", workflow)

    # Should detect write-all in nested dict
    write_all_findings = [f for f in findings if f.rule == "GHA-002-WRITE-ALL"]
    assert len(write_all_findings) == 1
    assert "write-all" in write_all_findings[0].message


def test_string_write_all_detection():
    """Test detection of write-all as string value."""
    workflow = """
name: Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    permissions: write-all
    steps:
      - uses: actions/checkout@v3
"""
    findings = analyze_github_workflow(".github/workflows/test.yml", workflow)

    # Should detect write-all as string
    write_all_findings = [f for f in findings if f.rule == "GHA-002-WRITE-ALL"]
    assert len(write_all_findings) == 1


def test_valid_permissions_no_write_all():
    """Test that valid permissions don't trigger false positives."""
    workflow = """
name: Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v3
"""
    findings = analyze_github_workflow(".github/workflows/test.yml", workflow)

    # Should not detect write-all
    write_all_findings = [f for f in findings if f.rule == "GHA-002-WRITE-ALL"]
    assert len(write_all_findings) == 0
