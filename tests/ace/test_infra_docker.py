"""Tests for Docker infrastructure detection."""

import pytest

from ace.skills.docker import (
    RULE_APT_NO_CLEANUP,
    RULE_LATEST_TAG,
    RULE_MISSING_USER,
    analyze_dockerfile,
    is_dockerfile,
)
from pathlib import Path


class TestIsDockerfile:
    """Tests for Dockerfile detection."""

    def test_dockerfile(self):
        """Test standard Dockerfile."""
        assert is_dockerfile(Path("Dockerfile"))

    def test_dockerfile_with_suffix(self):
        """Test Dockerfile with suffix."""
        assert is_dockerfile(Path("Dockerfile.prod"))

    def test_non_dockerfile(self):
        """Test non-Dockerfile."""
        assert not is_dockerfile(Path("test.py"))


class TestDockerAnalysis:
    """Tests for Dockerfile analysis."""

    def test_latest_tag_explicit(self):
        """Test detection of explicit :latest tag."""
        content = "FROM python:latest\nRUN echo hello"
        findings = analyze_dockerfile("Dockerfile", content)

        latest_findings = [f for f in findings if f.rule == RULE_LATEST_TAG]
        assert len(latest_findings) >= 1

    def test_latest_tag_implicit(self):
        """Test detection of implicit :latest (no tag)."""
        content = "FROM python\nRUN echo hello"
        findings = analyze_dockerfile("Dockerfile", content)

        latest_findings = [f for f in findings if f.rule == RULE_LATEST_TAG]
        assert len(latest_findings) >= 1

    def test_pinned_tag(self):
        """Test that pinned tags don't trigger."""
        content = "FROM python:3.11.5-slim\nUSER nonroot"
        findings = analyze_dockerfile("Dockerfile", content)

        latest_findings = [f for f in findings if f.rule == RULE_LATEST_TAG]
        assert len(latest_findings) == 0

    def test_missing_user(self):
        """Test detection of missing USER instruction."""
        content = "FROM python:3.11\nRUN echo hello"
        findings = analyze_dockerfile("Dockerfile", content)

        user_findings = [f for f in findings if f.rule == RULE_MISSING_USER]
        assert len(user_findings) == 1

    def test_has_user(self):
        """Test that USER instruction prevents finding."""
        content = "FROM python:3.11\nUSER nonroot\nRUN echo hello"
        findings = analyze_dockerfile("Dockerfile", content)

        user_findings = [f for f in findings if f.rule == RULE_MISSING_USER]
        assert len(user_findings) == 0

    def test_apt_no_y_flag(self):
        """Test detection of apt-get without -y."""
        content = "FROM ubuntu\nRUN apt-get install curl"
        findings = analyze_dockerfile("Dockerfile", content)

        apt_findings = [f for f in findings if f.rule == RULE_APT_NO_CLEANUP]
        assert len(apt_findings) >= 1

    def test_apt_no_cleanup(self):
        """Test detection of apt-get without cleanup."""
        content = "FROM ubuntu\nRUN apt-get install -y curl"
        findings = analyze_dockerfile("Dockerfile", content)

        apt_findings = [f for f in findings if f.rule == RULE_APT_NO_CLEANUP]
        assert len(apt_findings) >= 1

    def test_apt_with_cleanup(self):
        """Test that cleanup prevents finding."""
        content = "FROM ubuntu\nRUN apt-get install -y curl && rm -rf /var/lib/apt/lists/*"
        findings = analyze_dockerfile("Dockerfile", content)

        # Should have no apt cleanup findings
        apt_findings = [f for f in findings if "cleanup" in f.message.lower()]
        assert len(apt_findings) == 0

    def test_multiple_issues(self):
        """Test detection of multiple issues."""
        content = """FROM python:latest
RUN apt-get install -y curl
RUN echo hello
"""
        findings = analyze_dockerfile("Dockerfile", content)

        # Should have: latest tag + missing USER + apt issues
        assert len(findings) >= 3
