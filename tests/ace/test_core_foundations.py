"""Tests for ACE core foundations: UIR, Policy, and Safety modules."""

import tempfile
from pathlib import Path

import pytest

from ace.policy import (
    AUTO_THRESHOLD,
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    SUGGEST_THRESHOLD,
    Decision,
    PolicyEngine,
    decision,
    enforce_policy,
    rstar,
)
from ace.safety import content_hash, is_idempotent, verify_parse_py, verify_parseable
from ace.uir import Severity, create_uir, stable_id

# ============================================================================
# UIR Module Tests
# ============================================================================


class TestStableId:
    """Tests for stable_id() function."""

    def test_stable_id_deterministic(self):
        """Test that stable_id produces same result for same inputs."""
        id1 = stable_id("test.py", "unused-import", "import os")
        id2 = stable_id("test.py", "unused-import", "import os")
        assert id1 == id2

    def test_stable_id_format(self):
        """Test that stable_id returns correct format."""
        result = stable_id("test.py", "rule", "snippet")
        parts = result.split("-")
        assert len(parts) == 3
        assert all(len(p) == 8 for p in parts)
        assert all(c in "0123456789abcdef" for p in parts for c in p)

    def test_stable_id_different_inputs(self):
        """Test that different inputs produce different IDs."""
        id1 = stable_id("test.py", "rule1", "snippet1")
        id2 = stable_id("test.py", "rule2", "snippet1")
        id3 = stable_id("test.py", "rule1", "snippet2")
        id4 = stable_id("other.py", "rule1", "snippet1")

        assert id1 != id2
        assert id1 != id3
        assert id1 != id4

    def test_stable_id_empty_strings(self):
        """Test stable_id with empty strings."""
        result = stable_id("", "", "")
        assert isinstance(result, str)
        assert len(result.split("-")) == 3


class TestUnifiedIssue:
    """Tests for UnifiedIssue dataclass."""

    def test_create_uir_basic(self):
        """Test creating a basic UIR."""
        uir = create_uir("test.py", 42, "unused-import", "high", "Unused import 'os'")

        assert uir.file == "test.py"
        assert uir.line == 42
        assert uir.rule == "unused-import"
        assert uir.severity == Severity.HIGH
        assert uir.message == "Unused import 'os'"

    def test_create_uir_with_suggestion(self):
        """Test creating UIR with suggestion."""
        uir = create_uir(
            "test.py",
            10,
            "magic-number",
            "medium",
            "Magic number detected",
            suggestion="Extract to constant",
            snippet="x = 42",
        )

        assert uir.suggestion == "Extract to constant"
        assert uir.snippet == "x = 42"

    def test_create_uir_with_severity_enum(self):
        """Test creating UIR with Severity enum."""
        uir = create_uir("test.py", 1, "rule", Severity.CRITICAL, "Critical issue")

        assert uir.severity == Severity.CRITICAL

    def test_uir_to_dict(self):
        """Test UIR to_dict serialization."""
        uir = create_uir(
            "test.py",
            42,
            "unused-import",
            "high",
            "Unused import",
            suggestion="Remove it",
            snippet="import os",
        )

        data = uir.to_dict()

        assert data["file"] == "test.py"
        assert data["line"] == 42
        assert data["rule"] == "unused-import"
        assert data["severity"] == "high"
        assert data["message"] == "Unused import"
        assert data["suggestion"] == "Remove it"
        assert data["snippet"] == "import os"
        assert "stable_id" in data
        assert isinstance(data["stable_id"], str)

    def test_uir_immutable(self):
        """Test that UIR is immutable (frozen)."""
        uir = create_uir("test.py", 1, "rule", "info", "Test")

        with pytest.raises((AttributeError, TypeError)):  # FrozenInstanceError/dataclasses.FrozenInstanceError
            uir.file = "other.py"

    def test_severity_enum_values(self):
        """Test Severity enum has expected values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"


# ============================================================================
# Policy Module Tests
# ============================================================================


class TestRstar:
    """Tests for rstar() function."""

    def test_rstar_basic(self):
        """Test basic R* calculation."""
        result = rstar(0.9, 0.8)
        expected = DEFAULT_ALPHA * 0.9 + DEFAULT_BETA * 0.8
        assert abs(result - expected) < 0.01

    def test_rstar_default_weights(self):
        """Test R* with default α=0.7, β=0.3."""
        result = rstar(1.0, 1.0)
        assert result == 1.0

        result = rstar(0.0, 0.0)
        assert result == 0.0

    def test_rstar_custom_weights(self):
        """Test R* with custom weights."""
        result = rstar(0.5, 0.5, alpha=0.5, beta=0.5)
        assert result == 0.5

    def test_rstar_bounds_clamping(self):
        """Test that R* clamps inputs to [0, 1]."""
        result = rstar(1.5, -0.5)
        assert 0.0 <= result <= 1.0

    def test_rstar_high_severity_high_complexity(self):
        """Test R* with high severity and high complexity."""
        result = rstar(0.9, 0.8)
        assert result >= 0.85

    def test_rstar_low_severity_low_complexity(self):
        """Test R* with low severity and low complexity."""
        result = rstar(0.2, 0.1)
        assert result <= 0.2


class TestDecision:
    """Tests for decision() function."""

    def test_decision_auto(self):
        """Test decision returns AUTO for R* >= 0.70."""
        assert decision(0.85) == Decision.AUTO
        assert decision(0.70) == Decision.AUTO

    def test_decision_suggest(self):
        """Test decision returns SUGGEST for R* >= 0.50."""
        assert decision(0.60) == Decision.SUGGEST
        assert decision(0.50) == Decision.SUGGEST

    def test_decision_skip(self):
        """Test decision returns SKIP for R* < 0.50."""
        assert decision(0.40) == Decision.SKIP
        assert decision(0.0) == Decision.SKIP

    def test_decision_custom_thresholds(self):
        """Test decision with custom thresholds."""
        assert decision(0.75, auto_threshold=0.80, suggest_threshold=0.60) == Decision.SUGGEST
        assert decision(0.55, auto_threshold=0.80, suggest_threshold=0.60) == Decision.SKIP

    def test_decision_edge_cases(self):
        """Test decision at exact threshold boundaries."""
        assert decision(AUTO_THRESHOLD) == Decision.AUTO
        assert decision(SUGGEST_THRESHOLD) == Decision.SUGGEST
        assert decision(AUTO_THRESHOLD - 0.01) == Decision.SUGGEST
        assert decision(SUGGEST_THRESHOLD - 0.01) == Decision.SKIP


class TestPolicyEngine:
    """Tests for PolicyEngine class."""

    def test_policy_engine_defaults(self):
        """Test PolicyEngine with default values."""
        engine = PolicyEngine()

        assert engine.max_findings == 0
        assert engine.fail_on_critical is True
        assert engine.alpha == DEFAULT_ALPHA
        assert engine.beta == DEFAULT_BETA

    def test_policy_engine_no_violations(self):
        """Test policy evaluation with no violations."""
        engine = PolicyEngine(max_findings=10, fail_on_critical=False)
        findings = [
            {"severity": "medium", "rule": "test1"},
            {"severity": "low", "rule": "test2"},
        ]

        passed, violations = engine.evaluate(findings)

        assert passed is True
        assert len(violations) == 0

    def test_policy_engine_max_findings_exceeded(self):
        """Test policy fails when max findings exceeded."""
        engine = PolicyEngine(max_findings=2)
        findings = [
            {"severity": "low", "rule": "test1"},
            {"severity": "low", "rule": "test2"},
            {"severity": "low", "rule": "test3"},
        ]

        passed, violations = engine.evaluate(findings)

        assert passed is False
        assert len(violations) == 1
        assert "Exceeded max findings" in violations[0]

    def test_policy_engine_critical_findings(self):
        """Test policy fails on critical severity findings."""
        engine = PolicyEngine(fail_on_critical=True)
        findings = [
            {"severity": "critical", "rule": "dangerous-code"},
        ]

        passed, violations = engine.evaluate(findings)

        assert passed is False
        assert len(violations) == 1
        assert "critical" in violations[0].lower()

    def test_enforce_policy_function(self):
        """Test enforce_policy() convenience function."""
        findings = [{"severity": "critical", "rule": "test"}]
        config = {"fail_on_critical": True}

        passed, violations = enforce_policy(findings, config)

        assert passed is False
        assert len(violations) > 0


# ============================================================================
# Safety Module Tests
# ============================================================================


class TestVerifyParsePy:
    """Tests for verify_parse_py() function."""

    def test_verify_parse_py_valid_syntax(self):
        """Test verify_parse_py with valid Python syntax."""
        assert verify_parse_py("x = 1 + 2") is True
        assert verify_parse_py("def foo():\n    pass") is True
        assert verify_parse_py("import os\nimport sys") is True

    def test_verify_parse_py_invalid_syntax(self):
        """Test verify_parse_py with invalid Python syntax."""
        assert verify_parse_py("x = 1 +") is False
        assert verify_parse_py("def foo()") is False
        assert verify_parse_py("if True") is False

    def test_verify_parse_py_empty_string(self):
        """Test verify_parse_py with empty string."""
        assert verify_parse_py("") is True

    def test_verify_parse_py_complex_code(self):
        """Test verify_parse_py with complex valid code."""
        code = """
class MyClass:
    def __init__(self):
        self.value = 42

    def method(self, x):
        return x * 2
"""
        assert verify_parse_py(code) is True


class TestContentHash:
    """Tests for content_hash() function."""

    def test_content_hash_deterministic(self):
        """Test that content_hash is deterministic."""
        hash1 = content_hash("hello world")
        hash2 = content_hash("hello world")
        assert hash1 == hash2

    def test_content_hash_format(self):
        """Test content_hash format."""
        result = content_hash("test")
        assert result.startswith("sha256:")
        assert len(result) == 71  # "sha256:" (7) + 64 hex chars

    def test_content_hash_different_content(self):
        """Test different content produces different hashes."""
        hash1 = content_hash("content1")
        hash2 = content_hash("content2")
        assert hash1 != hash2

    def test_content_hash_empty_string(self):
        """Test content_hash with empty string."""
        result = content_hash("")
        assert result.startswith("sha256:")
        assert len(result) == 71

    def test_content_hash_known_value(self):
        """Test content_hash produces known SHA256 values."""
        # Known SHA256 of "hello world"
        result = content_hash("hello world")
        expected = "sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert result == expected


class TestIsIdempotent:
    """Tests for is_idempotent() function."""

    def test_is_idempotent_true(self):
        """Test is_idempotent with idempotent transformation."""

        def add_header(s):
            if s.startswith("# Header\n"):
                return s
            return "# Header\n" + s

        assert is_idempotent(add_header, "code") is True

    def test_is_idempotent_false(self):
        """Test is_idempotent with non-idempotent transformation."""

        def always_append(s):
            return s + "x"

        assert is_idempotent(always_append, "code") is False

    def test_is_idempotent_identity(self):
        """Test is_idempotent with identity function."""

        def identity(s):
            return s

        assert is_idempotent(identity, "anything") is True

    def test_is_idempotent_normalize_newlines(self):
        """Test is_idempotent with newline normalization."""

        def add_newline(s):
            return s + "\n"

        # With normalization (default)
        assert is_idempotent(add_newline, "code", normalize_newlines=True) is True

        # Without normalization
        assert is_idempotent(add_newline, "code", normalize_newlines=False) is False

    def test_is_idempotent_exception_handling(self):
        """Test is_idempotent handles exceptions gracefully."""

        def failing_transform(s):
            raise ValueError("Intentional failure")

        assert is_idempotent(failing_transform, "code") is False


class TestVerifyParseable:
    """Tests for verify_parseable() function."""

    def test_verify_parseable_valid_python_file(self):
        """Test verify_parseable with valid Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1 + 2\n")
            f.flush()
            path = f.name

        try:
            assert verify_parseable(path, "python") is True
        finally:
            Path(path).unlink()

    def test_verify_parseable_invalid_python_file(self):
        """Test verify_parseable with invalid Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1 +\n")
            f.flush()
            path = f.name

        try:
            assert verify_parseable(path, "python") is False
        finally:
            Path(path).unlink()

    def test_verify_parseable_nonexistent_file(self):
        """Test verify_parseable with non-existent file."""
        assert verify_parseable("/nonexistent/path.py", "python") is False

    def test_verify_parseable_other_languages(self):
        """Test verify_parseable with non-Python languages (stubs)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Markdown\n")
            f.flush()
            path = f.name

        try:
            # Stub implementation returns True for non-Python
            assert verify_parseable(path, "markdown") is True
        finally:
            Path(path).unlink()


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining multiple modules."""

    def test_uir_with_policy_decision(self):
        """Test creating UIR and making policy decision."""
        uir = create_uir(
            "test.py",
            42,
            "unused-import",
            "high",
            "Unused import",
            snippet="import os",
        )

        # High severity should map to high R* score
        r = rstar(0.9, 0.5)  # High severity, medium complexity
        dec = decision(r)

        assert dec in [Decision.AUTO, Decision.SUGGEST]
        assert uir.to_dict()["stable_id"] is not None

    def test_determinism_across_modules(self):
        """Test determinism across all modules."""
        # UIR stable_id should be deterministic
        id1 = stable_id("test.py", "rule", "snippet")
        id2 = stable_id("test.py", "rule", "snippet")
        assert id1 == id2

        # Policy rstar should be deterministic
        r1 = rstar(0.7, 0.5)
        r2 = rstar(0.7, 0.5)
        assert r1 == r2

        # Safety content_hash should be deterministic
        h1 = content_hash("content")
        h2 = content_hash("content")
        assert h1 == h2
