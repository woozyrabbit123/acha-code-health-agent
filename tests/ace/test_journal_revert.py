"""Tests for journal system and revert functionality."""

import hashlib
import tempfile
from pathlib import Path

from ace.journal import (
    Journal,
    build_revert_plan,
    find_latest_journal,
    read_journal,
)
from ace.safety import atomic_write


def test_journal_log_intent():
    """Test journal intent logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_dir = Path(tmpdir) / "journals"
        journal = Journal(run_id="test-001", journal_dir=journal_dir)

        content = b"original content"
        sha = hashlib.sha256(content).hexdigest()

        journal.log_intent(
            file="test.py",
            before_sha=sha,
            before_size=len(content),
            rule_ids=["PY-S101"],
            plan_id="plan-1",
            pre_image=content
        )

        journal.close()

        # Verify journal file exists
        journal_path = journal_dir / "test-001.jsonl"
        assert journal_path.exists()

        # Read and verify entries
        entries = read_journal(journal_path)
        assert len(entries) == 1
        assert entries[0].type == "intent"
        assert entries[0].file == "test.py"


def test_journal_log_success():
    """Test journal success logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_dir = Path(tmpdir) / "journals"
        journal = Journal(run_id="test-002", journal_dir=journal_dir)

        after_content = b"modified content"
        after_sha = hashlib.sha256(after_content).hexdigest()

        journal.log_success(
            file="test.py",
            after_sha=after_sha,
            after_size=len(after_content),
            receipt_id="receipt-1"
        )

        journal.close()

        # Verify journal file exists
        journal_path = journal_dir / "test-002.jsonl"
        assert journal_path.exists()

        # Read and verify entries
        entries = read_journal(journal_path)
        assert len(entries) == 1
        assert entries[0].type == "success"
        assert entries[0].file == "test.py"


def test_journal_log_revert():
    """Test journal revert logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_dir = Path(tmpdir) / "journals"
        journal = Journal(run_id="test-003", journal_dir=journal_dir)

        journal.log_revert(
            file="test.py",
            from_sha="abc123",
            to_sha="def456",
            reason="parse-fail"
        )

        journal.close()

        # Verify journal file exists
        journal_path = journal_dir / "test-003.jsonl"
        assert journal_path.exists()

        # Read and verify entries
        entries = read_journal(journal_path)
        assert len(entries) == 1
        assert entries[0].type == "revert"
        assert entries[0].data["reason"] == "parse-fail"


def test_build_revert_plan():
    """Test building revert plan from journal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_dir = Path(tmpdir) / "journals"
        journal = Journal(run_id="test-004", journal_dir=journal_dir)

        # Log a complete modification (intent + success)
        before_content = b"original content"
        before_sha = hashlib.sha256(before_content).hexdigest()

        journal.log_intent(
            file="test.py",
            before_sha=before_sha,
            before_size=len(before_content),
            rule_ids=["PY-S101"],
            plan_id="plan-1",
            pre_image=before_content
        )

        after_content = b"modified content"
        after_sha = hashlib.sha256(after_content).hexdigest()

        journal.log_success(
            file="test.py",
            after_sha=after_sha,
            after_size=len(after_content),
            receipt_id="receipt-1"
        )

        journal.close()

        # Build revert plan
        journal_path = journal_dir / "test-004.jsonl"
        revert_plan = build_revert_plan(journal_path)

        assert len(revert_plan) == 1
        assert revert_plan[0].file == "test.py"
        assert revert_plan[0].expected_current_sha == after_sha
        assert revert_plan[0].original_sha == before_sha


def test_find_latest_journal():
    """Test finding latest journal by modification time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_dir = Path(tmpdir) / "journals"
        journal_dir.mkdir()

        # Create multiple journals
        for i in range(3):
            journal_path = journal_dir / f"test-00{i}.jsonl"
            journal_path.write_text(f"test {i}\n")

        # Find latest
        latest = find_latest_journal(journal_dir)
        assert latest is not None
        assert latest.name.startswith("test-")


def test_revert_with_hash_verification():
    """Test revert with hash verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        journal_dir = Path(tmpdir) / "journals"

        # Create test file
        original_content = b"x = 1 + 2"
        test_file.write_bytes(original_content)
        before_sha = hashlib.sha256(original_content).hexdigest()

        # Create journal
        journal = Journal(run_id="test-005", journal_dir=journal_dir)

        journal.log_intent(
            file=str(test_file),
            before_sha=before_sha,
            before_size=len(original_content),
            rule_ids=["PY-S101"],
            plan_id="plan-1",
            pre_image=original_content
        )

        # Modify file
        modified_content = b"x = 1 + 3"
        atomic_write(test_file, modified_content)
        after_sha = hashlib.sha256(modified_content).hexdigest()

        journal.log_success(
            file=str(test_file),
            after_sha=after_sha,
            after_size=len(modified_content),
            receipt_id="receipt-1"
        )

        journal.close()

        # Build revert plan
        journal_path = journal_dir / "test-005.jsonl"
        revert_plan = build_revert_plan(journal_path)

        # Verify revert context
        assert len(revert_plan) == 1
        context = revert_plan[0]

        # Verify current file hash matches expected
        current_content = test_file.read_bytes()
        current_sha = hashlib.sha256(current_content).hexdigest()
        assert current_sha == context.expected_current_sha

        # Perform revert
        atomic_write(test_file, context.restore_content)

        # Verify file was restored (at least the first 4KB)
        restored_content = test_file.read_bytes()
        assert restored_content.startswith(original_content)


def test_journal_empty_when_no_entries():
    """Test journal returns empty list when no entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_path = Path(tmpdir) / "empty.jsonl"

        entries = read_journal(journal_path)
        assert entries == []


def test_revert_plan_empty_when_no_successes():
    """Test revert plan is empty when only intents logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_dir = Path(tmpdir) / "journals"
        journal = Journal(run_id="test-006", journal_dir=journal_dir)

        # Log intent but no success
        journal.log_intent(
            file="test.py",
            before_sha="abc123",
            before_size=100,
            rule_ids=["PY-S101"],
            plan_id="plan-1",
            pre_image=b"test"
        )

        journal.close()

        # Build revert plan
        journal_path = journal_dir / "test-006.jsonl"
        revert_plan = build_revert_plan(journal_path)

        # Should be empty since no success was logged
        assert len(revert_plan) == 0
