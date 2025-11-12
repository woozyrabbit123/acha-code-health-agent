"""Tests for Docker USER instruction in final stage."""
from ace.skills.docker import analyze_dockerfile


def test_user_required_in_final_stage():
    """Test that USER is required in the final build stage."""
    content = """FROM python:3.11-slim
USER nobody
FROM python:3.11-slim
RUN echo hi
"""

    findings = analyze_dockerfile("Dockerfile", content)

    # Should detect missing USER in final stage
    assert any("USER" in f.message for f in findings)


def test_user_present_in_final_stage_ok():
    """Test that USER in final stage is acceptable."""
    content = """FROM python:3.11-slim
RUN echo build
FROM python:3.11-slim
RUN echo runtime
USER nobody
"""

    findings = analyze_dockerfile("Dockerfile", content)

    # Should not flag USER issue
    user_findings = [f for f in findings if "USER" in f.message and "missing" in f.message.lower()]
    assert len(user_findings) == 0


def test_single_stage_with_user_ok():
    """Test single-stage Dockerfile with USER is OK."""
    content = """FROM python:3.11-slim
RUN pip install requests
USER nobody
CMD ["python", "app.py"]
"""

    findings = analyze_dockerfile("Dockerfile", content)

    # Should not flag USER issue
    user_findings = [f for f in findings if "USER" in f.message and "missing" in f.message.lower()]
    assert len(user_findings) == 0
