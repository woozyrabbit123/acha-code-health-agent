"""Test receipt verification."""

import json
import tempfile
from pathlib import Path

from ace.receipts import Receipt, create_receipt, verify_receipts


def test_verify_receipts_empty_ok():
    """Test verify_receipts with no journals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        failures = verify_receipts(tmpdir)

        # No journals = no failures
        assert failures == []


def test_verify_receipts_clean_ok():
    """Test verify_receipts with clean journal and matching files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create .ace/journals directory
        journals_dir = tmpdir / ".ace" / "journals"
        journals_dir.mkdir(parents=True, exist_ok=True)

        # Create a test file
        test_file = tmpdir / "test.py"
        before_content = "x = 1"
        after_content = "x = 2"
        test_file.write_text(after_content, encoding="utf-8")

        # Create a receipt
        receipt = create_receipt(
            plan_id="test-plan-1",
            file_path="test.py",
            before_content=before_content,
            after_content=after_content,
            parse_valid=True,
            invariants_met=True,
            estimated_risk=0.5,
            duration_ms=100,
        )

        # Write journal entry with receipt
        journal_file = journals_dir / "test-journal.jsonl"
        with open(journal_file, "w", encoding="utf-8") as f:
            entry = {
                "event": "success",
                "plan_id": "test-plan-1",
                "receipt": receipt.to_dict(),
            }
            f.write(json.dumps(entry) + "\n")

        # Verify receipts
        failures = verify_receipts(tmpdir)

        # Should pass verification
        assert failures == []


def test_verify_receipts_hash_mismatch():
    """Test verify_receipts detects hash mismatch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create .ace/journals directory
        journals_dir = tmpdir / ".ace" / "journals"
        journals_dir.mkdir(parents=True, exist_ok=True)

        # Create a test file
        test_file = tmpdir / "test.py"
        before_content = "x = 1"
        after_content = "x = 2"

        # File has different content than receipt expects
        test_file.write_text("x = 3", encoding="utf-8")

        # Create a receipt for after_content="x = 2"
        receipt = create_receipt(
            plan_id="test-plan-1",
            file_path="test.py",
            before_content=before_content,
            after_content=after_content,  # Receipt expects "x = 2"
            parse_valid=True,
            invariants_met=True,
            estimated_risk=0.5,
            duration_ms=100,
        )

        # Write journal entry with receipt
        journal_file = journals_dir / "test-journal.jsonl"
        with open(journal_file, "w", encoding="utf-8") as f:
            entry = {
                "event": "success",
                "plan_id": "test-plan-1",
                "receipt": receipt.to_dict(),
            }
            f.write(json.dumps(entry) + "\n")

        # Verify receipts
        failures = verify_receipts(tmpdir)

        # Should detect hash mismatch
        assert len(failures) == 1
        assert "Hash mismatch" in failures[0]


def test_verify_receipts_missing_file():
    """Test verify_receipts detects missing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create .ace/journals directory
        journals_dir = tmpdir / ".ace" / "journals"
        journals_dir.mkdir(parents=True, exist_ok=True)

        # Create a receipt for a file that doesn't exist
        receipt = create_receipt(
            plan_id="test-plan-1",
            file_path="missing.py",
            before_content="x = 1",
            after_content="x = 2",
            parse_valid=True,
            invariants_met=True,
            estimated_risk=0.5,
            duration_ms=100,
        )

        # Write journal entry with receipt
        journal_file = journals_dir / "test-journal.jsonl"
        with open(journal_file, "w", encoding="utf-8") as f:
            entry = {
                "event": "success",
                "plan_id": "test-plan-1",
                "receipt": receipt.to_dict(),
            }
            f.write(json.dumps(entry) + "\n")

        # Verify receipts
        failures = verify_receipts(tmpdir)

        # Should detect missing file
        assert len(failures) == 1
        assert "no longer exists" in failures[0]
