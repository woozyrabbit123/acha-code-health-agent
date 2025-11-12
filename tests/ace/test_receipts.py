"""Tests for receipts generation and validation."""

import json
import tempfile
from pathlib import Path

import pytest

from ace.export import validate_against_schema
from ace.kernel import run_apply
from ace.receipts import (
    Receipt,
    create_receipt,
    is_idempotent_transformation,
    verify_receipt,
)


class TestReceiptCreation:
    """Test receipt creation and basic operations."""

    def test_create_receipt_basic(self):
        """Test creating a basic receipt."""
        receipt = create_receipt(
            plan_id="test-plan-123",
            file_path="test.py",
            before_content="x = 1\n",
            after_content="x = 2\n",
            parse_valid=True,
            invariants_met=True,
            estimated_risk=0.3,
            duration_ms=50,
        )

        assert receipt.plan_id == "test-plan-123"
        assert receipt.file == "test.py"
        assert len(receipt.before_hash) == 64  # 64 hex chars (no prefix)
        assert len(receipt.after_hash) == 64
        assert receipt.parse_valid is True
        assert receipt.invariants_met is True
        assert receipt.estimated_risk == 0.3
        assert receipt.duration_ms == 50
        assert receipt.timestamp.endswith("Z")  # UTC timestamp

    def test_create_receipt_different_hashes(self):
        """Test that different content produces different hashes."""
        receipt1 = create_receipt(
            "p1", "f.py", "old1", "new1", True, True, 0.1, 10
        )
        receipt2 = create_receipt(
            "p2", "f.py", "old2", "new2", True, True, 0.1, 10
        )

        assert receipt1.before_hash != receipt2.before_hash
        assert receipt1.after_hash != receipt2.after_hash

    def test_create_receipt_deterministic_hashes(self):
        """Test that same content produces same hash."""
        receipt1 = create_receipt(
            "p1", "f.py", "content", "new_content", True, True, 0.1, 10
        )
        receipt2 = create_receipt(
            "p1", "f.py", "content", "new_content", True, True, 0.1, 10
        )

        # Same content = same hash
        assert receipt1.before_hash == receipt2.before_hash
        assert receipt1.after_hash == receipt2.after_hash

    def test_receipt_to_dict(self):
        """Test converting receipt to dictionary."""
        receipt = create_receipt(
            "plan-456", "api.py", "old_code", "new_code", True, True, 0.5, 100
        )
        data = receipt.to_dict()

        assert data["plan_id"] == "plan-456"
        assert data["file"] == "api.py"
        assert "before_hash" in data
        assert "after_hash" in data
        assert data["parse_valid"] is True
        assert data["invariants_met"] is True
        assert data["estimated_risk"] == 0.5
        assert data["duration_ms"] == 100
        assert "timestamp" in data

    def test_receipt_from_dict(self):
        """Test creating receipt from dictionary."""
        data = {
            "plan_id": "plan-789",
            "file": "module.py",
            "before_hash": "a" * 64,  # Just hex, no prefix
            "after_hash": "b" * 64,
            "parse_valid": False,
            "invariants_met": False,
            "estimated_risk": 0.9,
            "duration_ms": 200,
            "timestamp": "2025-01-12T10:00:00Z",
        }

        receipt = Receipt.from_dict(data)

        assert receipt.plan_id == "plan-789"
        assert receipt.file == "module.py"
        assert receipt.before_hash == "a" * 64
        assert receipt.after_hash == "b" * 64
        assert receipt.parse_valid is False
        assert receipt.invariants_met is False
        assert receipt.estimated_risk == 0.9
        assert receipt.duration_ms == 200


class TestReceiptValidation:
    """Test receipt verification and validation."""

    def test_verify_receipt_matches(self):
        """Test verifying receipt with matching content."""
        receipt = create_receipt(
            "p1", "f.py", "old", "new_content", True, True, 0.1, 50
        )

        # Verify with matching content
        assert verify_receipt(receipt, "new_content") is True

    def test_verify_receipt_mismatch(self):
        """Test verifying receipt with modified content."""
        receipt = create_receipt(
            "p1", "f.py", "old", "new_content", True, True, 0.1, 50
        )

        # Verify with different content
        assert verify_receipt(receipt, "modified_content") is False

    def test_is_idempotent_transformation_true(self):
        """Test detecting idempotent transformation."""
        assert is_idempotent_transformation("x = 1", "x = 1") is True

    def test_is_idempotent_transformation_false(self):
        """Test detecting non-idempotent transformation."""
        assert is_idempotent_transformation("x = 1", "x = 2") is False


class TestReceiptSchemaCompliance:
    """Test that receipts comply with JSON Schema."""

    def test_receipt_validates_against_schema(self):
        """Test that receipt dict validates against schema."""
        receipt = create_receipt(
            "plan-abc", "test.py", "before", "after", True, True, 0.2, 75
        )
        data = receipt.to_dict()

        valid, errors = validate_against_schema(data, "receipt")
        assert valid, f"Validation errors: {errors}"

    def test_receipt_json_serialization(self):
        """Test that receipt can be serialized to JSON."""
        receipt = create_receipt(
            "plan-xyz", "module.py", "old_code", "new_code", True, False, 0.7, 150
        )
        data = receipt.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(data, indent=2, sort_keys=True)
        assert json_str

        # Should be deserializable
        loaded = json.loads(json_str)
        assert loaded["plan_id"] == "plan-xyz"

    def test_receipt_round_trip(self):
        """Test receipt serialization round-trip."""
        original = create_receipt(
            "plan-round", "app.py", "v1", "v2", True, True, 0.4, 120
        )

        # to_dict -> JSON -> from_dict
        data = original.to_dict()
        json_str = json.dumps(data)
        loaded_data = json.loads(json_str)
        restored = Receipt.from_dict(loaded_data)

        assert restored.plan_id == original.plan_id
        assert restored.file == original.file
        assert restored.before_hash == original.before_hash
        assert restored.after_hash == original.after_hash
        assert restored.parse_valid == original.parse_valid
        assert restored.invariants_met == original.invariants_met
        assert restored.estimated_risk == original.estimated_risk
        assert restored.duration_ms == original.duration_ms


class TestReceiptsIntegration:
    """Integration tests for receipts with kernel."""

    def test_run_apply_generates_receipts(self):
        """Test that run_apply generates receipts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def foo():
    try:
        return 1
    except:
        return 0
""")

            exit_code, receipts = run_apply(Path(tmpdir), dry_run=False)

            assert exit_code == 0
            assert len(receipts) > 0

            receipt = receipts[0]
            assert receipt.plan_id
            assert receipt.file == str(test_file)
            assert len(receipt.before_hash) == 64  # Hex only
            assert len(receipt.after_hash) == 64
            assert receipt.parse_valid is True
            assert 0.0 <= receipt.estimated_risk <= 1.0
            assert receipt.duration_ms >= 0

    def test_receipts_have_valid_hashes(self):
        """Test that receipt hashes are valid SHA256."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import os
import sys

def bar():
    pass
""")

            exit_code, receipts = run_apply(Path(tmpdir), dry_run=False)

            if receipts:  # Only test if receipts were generated
                receipt = receipts[0]

                # Should be 64 chars: hex only (no prefix)
                assert len(receipt.before_hash) == 64
                assert len(receipt.after_hash) == 64

                # Verify it's valid hex
                assert all(c in "0123456789abcdef" for c in receipt.before_hash)
                assert all(c in "0123456789abcdef" for c in receipt.after_hash)

    def test_idempotent_apply_preserves_hash(self):
        """Test that applying twice produces same after_hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def baz():
    try:
        x = 1
    except:
        x = 0
""")

            # First apply
            exit_code1, receipts1 = run_apply(Path(tmpdir), dry_run=False)

            if receipts1:
                first_after_hash = receipts1[0].after_hash

                # Read the modified content
                modified_content = test_file.read_text()

                # Second apply on already-fixed code
                exit_code2, receipts2 = run_apply(Path(tmpdir), dry_run=False)

                # If second apply generated receipts, the before hash should match first after hash
                if receipts2:
                    assert receipts2[0].before_hash == first_after_hash

    def test_receipts_validate_against_schema(self):
        """Test that generated receipts validate against schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def qux():
    try:
        pass
    except:
        pass
""")

            exit_code, receipts = run_apply(Path(tmpdir), dry_run=False)

            for receipt in receipts:
                data = receipt.to_dict()
                valid, errors = validate_against_schema(data, "receipt")
                assert valid, f"Receipt validation failed: {errors}"

    def test_receipts_json_export(self):
        """Test that receipts can be exported to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import sys
import os

x = 1
""")

            exit_code, receipts = run_apply(Path(tmpdir), dry_run=False)

            if receipts:
                # Export to JSON
                receipts_json = json.dumps(
                    [r.to_dict() for r in receipts],
                    indent=2,
                    sort_keys=True,
                )

                # Should be valid JSON
                loaded = json.loads(receipts_json)
                assert isinstance(loaded, list)

                # Each item should validate
                for item in loaded:
                    valid, _ = validate_against_schema(item, "receipt")
                    assert valid

    def test_receipt_captures_timing(self):
        """Test that receipts capture timing information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def timing_test():
    try:
        return 42
    except:
        return 0
""")

            exit_code, receipts = run_apply(Path(tmpdir), dry_run=False)

            if receipts:
                receipt = receipts[0]

                # Duration should be non-negative
                assert receipt.duration_ms >= 0

                # Timestamp should be ISO 8601 format
                assert "T" in receipt.timestamp
                assert receipt.timestamp.endswith("Z")


class TestReceiptDeterminism:
    """Test deterministic properties of receipts."""

    def test_same_content_same_hash(self):
        """Test that identical content produces identical hash."""
        content = "def foo():\n    return 42\n"

        receipt1 = create_receipt("p1", "f.py", "old", content, True, True, 0.1, 10)
        receipt2 = create_receipt("p2", "f.py", "old", content, True, True, 0.2, 20)

        # Same after content should have same after hash
        assert receipt1.after_hash == receipt2.after_hash

    def test_different_content_different_hash(self):
        """Test that different content produces different hash."""
        receipt1 = create_receipt("p1", "f.py", "old", "new1", True, True, 0.1, 10)
        receipt2 = create_receipt("p1", "f.py", "old", "new2", True, True, 0.1, 10)

        # Different after content should have different after hash
        assert receipt1.after_hash != receipt2.after_hash

    def test_receipt_json_deterministic_ordering(self):
        """Test that JSON serialization has deterministic ordering."""
        receipt = create_receipt(
            "plan-det", "det.py", "before", "after", True, True, 0.5, 100
        )

        # Serialize twice with sort_keys
        json1 = json.dumps(receipt.to_dict(), indent=2, sort_keys=True)
        json2 = json.dumps(receipt.to_dict(), indent=2, sort_keys=True)

        # Should be identical
        assert json1 == json2
