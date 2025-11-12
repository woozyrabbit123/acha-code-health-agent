"""Tests for JSON Schema validation of UIR data structures."""

import json
import pytest

from ace.export import load_schema, validate_against_schema
from ace.uir import UnifiedIssue, Severity, create_uir
from ace.skills.python import Edit, EditPlan


class TestSchemaLoading:
    """Test schema loading and caching."""

    def test_load_unified_issue_schema(self):
        """Test loading UnifiedIssue schema."""
        schema = load_schema("unified_issue")
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["title"] == "UnifiedIssue"
        assert "properties" in schema
        assert "file" in schema["properties"]
        assert "line" in schema["properties"]
        assert "rule" in schema["properties"]

    def test_load_edit_schema(self):
        """Test loading Edit schema."""
        schema = load_schema("edit")
        assert schema["title"] == "Edit"
        assert "file" in schema["properties"]
        assert "op" in schema["properties"]
        assert schema["properties"]["op"]["enum"] == ["replace", "insert", "delete"]

    def test_load_edit_plan_schema(self):
        """Test loading EditPlan schema."""
        schema = load_schema("edit_plan")
        assert schema["title"] == "EditPlan"
        assert "id" in schema["properties"]
        assert "findings" in schema["properties"]
        assert "edits" in schema["properties"]

    def test_load_receipt_schema(self):
        """Test loading Receipt schema."""
        schema = load_schema("receipt")
        assert schema["title"] == "Receipt"
        assert "plan_id" in schema["properties"]
        assert "before_hash" in schema["properties"]
        assert "after_hash" in schema["properties"]

    def test_schema_caching(self):
        """Test that schemas are cached after first load."""
        schema1 = load_schema("unified_issue")
        schema2 = load_schema("unified_issue")
        # Should be the exact same object (cached)
        assert schema1 is schema2


class TestUnifiedIssueValidation:
    """Test UnifiedIssue schema validation."""

    def test_valid_unified_issue(self):
        """Test validation of a valid UnifiedIssue."""
        uir = create_uir(
            file="test.py",
            line=42,
            rule="PY-E201-BROAD-EXCEPT",
            severity="high",
            message="Bare except clause found",
            suggestion="Replace with 'except Exception:'",
            snippet="except:",
        )
        data = uir.to_dict()

        valid, errors = validate_against_schema(data, "unified_issue")
        assert valid, f"Validation errors: {errors}"
        assert errors == []

    def test_invalid_rule_format(self):
        """Test validation fails for invalid rule format."""
        data = {
            "file": "test.py",
            "line": 1,
            "rule": "invalid",  # Doesn't match pattern
            "severity": "high",
            "message": "test",
            "stable_id": "01234567-89abcdef-01234567",
        }

        valid, errors = validate_against_schema(data, "unified_issue")
        assert not valid
        assert len(errors) > 0

    def test_invalid_severity(self):
        """Test validation fails for invalid severity."""
        data = {
            "file": "test.py",
            "line": 1,
            "rule": "PY-E201-TEST",
            "severity": "unknown",  # Not in enum
            "message": "test",
            "stable_id": "01234567-89abcdef-01234567",
        }

        valid, errors = validate_against_schema(data, "unified_issue")
        assert not valid
        assert any("severity" in err.lower() for err in errors)

    def test_missing_required_field(self):
        """Test validation fails when required fields are missing."""
        data = {
            "file": "test.py",
            "line": 1,
            # Missing 'rule'
            "severity": "high",
            "message": "test",
        }

        valid, errors = validate_against_schema(data, "unified_issue")
        assert not valid
        assert any("required" in err.lower() or "rule" in err.lower() for err in errors)

    def test_additional_properties_rejected(self):
        """Test that unknown properties are rejected."""
        data = {
            "file": "test.py",
            "line": 1,
            "rule": "PY-E201-TEST",
            "severity": "high",
            "message": "test",
            "stable_id": "01234567-89abcdef-01234567",
            "unknown_field": "should fail",  # Extra field
        }

        valid, errors = validate_against_schema(data, "unified_issue")
        assert not valid
        assert any("additional" in err.lower() for err in errors)


class TestEditValidation:
    """Test Edit schema validation."""

    def test_valid_edit(self):
        """Test validation of a valid Edit."""
        edit = Edit(
            file="test.py",
            start_line=1,
            end_line=10,
            op="replace",
            payload="new code",
        )
        data = {
            "file": edit.file,
            "start_line": edit.start_line,
            "end_line": edit.end_line,
            "op": edit.op,
            "payload": edit.payload,
        }

        valid, errors = validate_against_schema(data, "edit")
        assert valid, f"Validation errors: {errors}"

    def test_invalid_op(self):
        """Test validation fails for invalid op."""
        data = {
            "file": "test.py",
            "start_line": 1,
            "end_line": 10,
            "op": "invalid_op",  # Not in enum
            "payload": "test",
        }

        valid, errors = validate_against_schema(data, "edit")
        assert not valid
        assert any("op" in err.lower() for err in errors)


class TestEditPlanValidation:
    """Test EditPlan schema validation."""

    def test_valid_edit_plan(self):
        """Test validation of a valid EditPlan."""
        uir = create_uir(
            file="test.py",
            line=1,
            rule="PY-E201-TEST",
            severity="low",
            message="test",
            snippet="x",
        )
        plan = EditPlan(
            id="test-plan-123",
            findings=[uir],
            edits=[
                Edit(
                    file="test.py",
                    start_line=1,
                    end_line=1,
                    op="replace",
                    payload="fixed",
                )
            ],
            invariants=["must_parse"],
            estimated_risk=0.5,
        )
        data = plan.to_dict()

        valid, errors = validate_against_schema(data, "edit_plan")
        assert valid, f"Validation errors: {errors}"

    def test_invalid_risk_range(self):
        """Test validation fails for risk outside [0.0, 1.0]."""
        data = {
            "id": "test-plan",
            "findings": [],
            "edits": [],
            "invariants": [],
            "estimated_risk": 1.5,  # Out of range
        }

        valid, errors = validate_against_schema(data, "edit_plan")
        assert not valid
        assert any("estimated_risk" in err.lower() or "maximum" in err.lower() for err in errors)


class TestReceiptValidation:
    """Test Receipt schema validation."""

    def test_valid_receipt(self):
        """Test validation of a valid Receipt."""
        data = {
            "plan_id": "test-plan-123",
            "file": "test.py",
            "before_hash": "a" * 64,  # Valid SHA256 hex
            "after_hash": "b" * 64,
            "parse_valid": True,
            "invariants_met": True,
            "estimated_risk": 0.3,
            "duration_ms": 150,
            "timestamp": "2025-01-12T10:30:00Z",
        }

        valid, errors = validate_against_schema(data, "receipt")
        assert valid, f"Validation errors: {errors}"

    def test_invalid_hash_format(self):
        """Test validation fails for invalid SHA256 hash format."""
        data = {
            "plan_id": "test-plan-123",
            "file": "test.py",
            "before_hash": "invalid",  # Not 64 hex chars
            "after_hash": "b" * 64,
            "parse_valid": True,
            "invariants_met": True,
            "estimated_risk": 0.3,
            "duration_ms": 150,
            "timestamp": "2025-01-12T10:30:00Z",
        }

        valid, errors = validate_against_schema(data, "receipt")
        assert not valid
        assert any("before_hash" in err.lower() or "pattern" in err.lower() for err in errors)

    def test_negative_duration_rejected(self):
        """Test validation fails for negative duration."""
        data = {
            "plan_id": "test-plan-123",
            "file": "test.py",
            "before_hash": "a" * 64,
            "after_hash": "b" * 64,
            "parse_valid": True,
            "invariants_met": True,
            "estimated_risk": 0.3,
            "duration_ms": -1,  # Invalid
            "timestamp": "2025-01-12T10:30:00Z",
        }

        valid, errors = validate_against_schema(data, "receipt")
        assert not valid
        assert any("duration" in err.lower() or "minimum" in err.lower() for err in errors)


class TestRoundTripSerialization:
    """Test round-trip serialization with validation."""

    def test_unified_issue_round_trip(self):
        """Test UnifiedIssue can be serialized and validated."""
        uir = create_uir(
            file="api.py",
            line=123,
            rule="PY-I101-IMPORT-SORT",
            severity="low",
            message="Imports not sorted alphabetically",
            suggestion="Run import sort fixer",
            snippet="import os\nimport abc",
        )

        # Serialize
        data = uir.to_dict()
        json_str = json.dumps(data, indent=2, sort_keys=True)

        # Deserialize
        loaded = json.loads(json_str)

        # Validate
        valid, errors = validate_against_schema(loaded, "unified_issue")
        assert valid, f"Round-trip validation failed: {errors}"

        # Check field preservation
        assert loaded["file"] == "api.py"
        assert loaded["line"] == 123
        assert loaded["rule"] == "PY-I101-IMPORT-SORT"
        assert loaded["severity"] == "low"

    def test_edit_plan_round_trip(self):
        """Test EditPlan can be serialized and validated."""
        uir = create_uir("test.py", 1, "PY-E201-TEST", "low", "test", snippet="x")
        plan = EditPlan(
            id="plan-456",
            findings=[uir],
            edits=[Edit("test.py", 1, 1, "replace", "fixed")],
            invariants=["must_parse", "idempotent"],
            estimated_risk=0.2,
        )

        # Serialize
        data = plan.to_dict()
        json_str = json.dumps(data, indent=2, sort_keys=True)

        # Deserialize
        loaded = json.loads(json_str)

        # Validate
        valid, errors = validate_against_schema(loaded, "edit_plan")
        assert valid, f"Round-trip validation failed: {errors}"

    def test_deterministic_ordering(self):
        """Test that serialization order is deterministic."""
        uir = create_uir("test.py", 1, "PY-E201-TEST", "low", "msg", snippet="x")

        # Serialize twice
        data1 = uir.to_dict()
        json1 = json.dumps(data1, indent=2, sort_keys=True)

        data2 = uir.to_dict()
        json2 = json.dumps(data2, indent=2, sort_keys=True)

        # Should be byte-identical
        assert json1 == json2
