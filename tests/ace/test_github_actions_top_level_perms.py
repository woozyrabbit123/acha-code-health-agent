"""Tests for GitHub Actions top-level permissions detection."""
from ace.skills.github_actions import analyze_github_workflow


def test_detect_top_level_write_all():
    """Test detection of top-level write-all permissions."""
    content = """
name: CI
on: push
permissions: write-all
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""

    findings = analyze_github_workflow(".github/workflows/ci.yml", content)

    # Should detect top-level write-all
    assert any("write-all" in f.message.lower() and "top level" in f.message.lower()
               for f in findings)


def test_detect_top_level_write_scopes():
    """Test detection of top-level write permissions to specific scopes."""
    content = """
name: CI
on: push
permissions:
  contents: write
  issues: write
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""

    findings = analyze_github_workflow(".github/workflows/ci.yml", content)

    # Should detect write permissions at top level
    write_findings = [f for f in findings if "write" in f.message.lower() and "top level" in f.message.lower()]
    assert len(write_findings) > 0


def test_minimal_permissions_ok():
    """Test that minimal read permissions are OK."""
    content = """
name: CI
on: push
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""

    findings = analyze_github_workflow(".github/workflows/ci.yml", content)

    # Should not flag read-only permissions
    perm_findings = [f for f in findings if "GHA-002" in f.rule]
    assert len(perm_findings) == 0
