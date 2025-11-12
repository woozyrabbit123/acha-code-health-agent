"""Test Docker multi-stage USER tracking."""

import pytest
from ace.skills.docker import analyze_dockerfile


def test_multi_stage_user_reset():
    """Test that USER tracking resets for each FROM stage."""
    dockerfile = """
FROM python:3.11
USER appuser
COPY . /app

FROM node:18
RUN npm install
"""
    findings = analyze_dockerfile("Dockerfile", dockerfile)

    # Should have 1 MISSING-USER finding (for the second stage)
    missing_user_findings = [f for f in findings if f.rule == "DOCK-002-MISSING-USER"]
    assert len(missing_user_findings) == 1
    assert missing_user_findings[0].line == 5  # Line with "FROM node:18"


def test_multi_stage_both_have_user():
    """Test that no findings when both stages have USER."""
    dockerfile = """
FROM python:3.11
USER appuser

FROM node:18
USER nodeuser
"""
    findings = analyze_dockerfile("Dockerfile", dockerfile)

    # Should have no MISSING-USER findings
    missing_user_findings = [f for f in findings if f.rule == "DOCK-002-MISSING-USER"]
    assert len(missing_user_findings) == 0


def test_multi_stage_neither_have_user():
    """Test that both stages report missing USER."""
    dockerfile = """
FROM python:3.11
RUN echo "stage 1"

FROM node:18
RUN echo "stage 2"
"""
    findings = analyze_dockerfile("Dockerfile", dockerfile)

    # Should have 1 MISSING-USER finding (only reports on last FROM)
    missing_user_findings = [f for f in findings if f.rule == "DOCK-002-MISSING-USER"]
    assert len(missing_user_findings) == 1
