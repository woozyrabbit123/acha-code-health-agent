"""Tests for receipt integrity verification."""

import hashlib
import tempfile
from pathlib import Path

from ace.kernel import verify_receipts
from ace.receipts import Receipt


def test_verify_receipts_empty_list():
    """Test verifying empty receipt list."""
    receipts = []
    result = verify_receipts(receipts)

    assert result is True


def test_verify_receipts_valid():
    """Test verifying valid receipts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        content = "x = 1 + 2"
        test_file.write_text(content)

        # Compute hash
        content_bytes = content.encode("utf-8")
        after_sha = hashlib.sha256(content_bytes).hexdigest()

        # Create receipt
        receipt = Receipt(
            plan_id="p1",
            file=str(test_file),
            before_hash="before-sha",
            after_hash=after_sha,  # Should match current file
            parse_valid=True,
            invariants_met=True,
            estimated_risk=0.1,
            duration_ms=100,
            timestamp="2024-01-01T00:00:00Z"
        )

        result = verify_receipts([receipt])

        assert result is True


def test_verify_receipts_file_missing():
    """Test verifying receipt for missing file."""
    receipt = Receipt(
        plan_id="p1",
        file="/nonexistent/file.py",
        before_hash="before-sha",
        after_hash="after-sha",
        parse_valid=True,
        invariants_met=True,
        estimated_risk=0.1,
        duration_ms=100,
        timestamp="2024-01-01T00:00:00Z"
    )

    result = verify_receipts([receipt])

    # Should fail because file doesn't exist
    assert result is False


def test_verify_receipts_hash_mismatch():
    """Test verifying receipt with hash mismatch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1 + 2")

        # Create receipt with wrong hash
        receipt = Receipt(
            plan_id="p1",
            file=str(test_file),
            before_hash="before-sha",
            after_hash="wrong-sha-that-does-not-match-file-content-at-all",
            parse_valid=True,
            invariants_met=True,
            estimated_risk=0.1,
            duration_ms=100,
            timestamp="2024-01-01T00:00:00Z"
        )

        result = verify_receipts([receipt])

        # Should fail because hash doesn't match
        assert result is False


def test_verify_receipts_multiple():
    """Test verifying multiple receipts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two files with receipts
        file1 = Path(tmpdir) / "test1.py"
        file2 = Path(tmpdir) / "test2.py"

        content1 = "x = 1"
        content2 = "y = 2"

        file1.write_text(content1)
        file2.write_text(content2)

        hash1 = hashlib.sha256(content1.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(content2.encode("utf-8")).hexdigest()

        receipts = [
            Receipt(
                plan_id="p1",
                file=str(file1),
                before_hash="b1",
                after_hash=hash1,
                parse_valid=True,
                invariants_met=True,
                estimated_risk=0.1,
                duration_ms=100,
                timestamp="2024-01-01T00:00:00Z"
            ),
            Receipt(
                plan_id="p2",
                file=str(file2),
                before_hash="b2",
                after_hash=hash2,
                parse_valid=True,
                invariants_met=True,
                estimated_risk=0.1,
                duration_ms=100,
                timestamp="2024-01-01T00:00:00Z"
            ),
        ]

        result = verify_receipts(receipts)

        assert result is True


def test_verify_receipts_one_invalid():
    """Test verifying receipts where one is invalid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create one valid and one invalid receipt
        valid_file = Path(tmpdir) / "valid.py"
        valid_file.write_text("x = 1")
        valid_hash = hashlib.sha256("x = 1".encode("utf-8")).hexdigest()

        receipts = [
            Receipt(
                plan_id="p1",
                file=str(valid_file),
                before_hash="b1",
                after_hash=valid_hash,
                parse_valid=True,
                invariants_met=True,
                estimated_risk=0.1,
                duration_ms=100,
                timestamp="2024-01-01T00:00:00Z"
            ),
            Receipt(
                plan_id="p2",
                file="/nonexistent/file.py",
                before_hash="b2",
                after_hash="invalid",
                parse_valid=True,
                invariants_met=True,
                estimated_risk=0.1,
                duration_ms=100,
                timestamp="2024-01-01T00:00:00Z"
            ),
        ]

        result = verify_receipts(receipts)

        # Should fail because one receipt is invalid
        assert result is False
