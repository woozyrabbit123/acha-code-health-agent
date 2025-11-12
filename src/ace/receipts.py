"""Receipt generation for tracking refactoring applications.

Receipts provide cryptographic proof and validation records of code transformations.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from ace.safety import content_hash


@dataclass
class Receipt:
    """
    Receipt for a single applied refactoring.

    Attributes:
        plan_id: Identifier of the EditPlan that was applied
        file: Path to file that was modified
        before_hash: SHA256 hash of content before transformation
        after_hash: SHA256 hash of content after transformation
        parse_valid: Whether the transformed code parses successfully
        invariants_met: Whether all specified invariants were satisfied
        estimated_risk: Risk estimate from the EditPlan [0.0, 1.0]
        duration_ms: Time taken to apply the transformation in milliseconds
        timestamp: ISO 8601 timestamp of when transformation was applied
        policy_hash: Hash of policy configuration used (optional, v0.7+)
    """

    plan_id: str
    file: str
    before_hash: str
    after_hash: str
    parse_valid: bool
    invariants_met: bool
    estimated_risk: float
    duration_ms: int
    timestamp: str
    policy_hash: str = ""

    def to_dict(self) -> dict:
        """Convert receipt to dictionary for JSON serialization."""
        result = {
            "plan_id": self.plan_id,
            "file": self.file,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "parse_valid": self.parse_valid,
            "invariants_met": self.invariants_met,
            "estimated_risk": self.estimated_risk,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }
        # Only include policy_hash if present (v0.7+)
        if self.policy_hash:
            result["policy_hash"] = self.policy_hash
        return result

    @staticmethod
    def from_dict(data: dict) -> "Receipt":
        """Create receipt from dictionary."""
        return Receipt(
            plan_id=data["plan_id"],
            file=data["file"],
            before_hash=data["before_hash"],
            after_hash=data["after_hash"],
            parse_valid=data["parse_valid"],
            invariants_met=data["invariants_met"],
            estimated_risk=data["estimated_risk"],
            duration_ms=data["duration_ms"],
            timestamp=data["timestamp"],
            policy_hash=data.get("policy_hash", ""),
        )


def create_receipt(
    plan_id: str,
    file_path: str,
    before_content: str,
    after_content: str,
    parse_valid: bool,
    invariants_met: bool,
    estimated_risk: float,
    duration_ms: int,
    policy_hash: str = "",
) -> Receipt:
    """
    Create a receipt for an applied refactoring.

    Args:
        plan_id: Identifier of the EditPlan
        file_path: Path to file that was modified
        before_content: Content before transformation
        after_content: Content after transformation
        parse_valid: Whether transformed code parses successfully
        invariants_met: Whether all invariants were satisfied
        estimated_risk: Risk estimate [0.0, 1.0]
        duration_ms: Duration of transformation in milliseconds
        policy_hash: Hash of policy configuration (optional, v0.7+)

    Returns:
        Receipt object with all fields populated

    Examples:
        >>> receipt = create_receipt(
        ...     plan_id="plan-123",
        ...     file_path="foo.py",
        ...     before_content="x = 1",
        ...     after_content="x = 2",
        ...     parse_valid=True,
        ...     invariants_met=True,
        ...     estimated_risk=0.1,
        ...     duration_ms=50
        ... )
        >>> receipt.plan_id
        'plan-123'
        >>> len(receipt.before_hash)
        64
    """
    # Calculate SHA256 hashes (strip "sha256:" prefix for schema compliance)
    before_hash_full = content_hash(before_content)
    after_hash_full = content_hash(after_content)

    # Strip "sha256:" prefix if present
    before_hash = before_hash_full.replace("sha256:", "") if before_hash_full.startswith("sha256:") else before_hash_full
    after_hash = after_hash_full.replace("sha256:", "") if after_hash_full.startswith("sha256:") else after_hash_full

    # Generate ISO 8601 timestamp in UTC with Z suffix
    timestamp = datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    return Receipt(
        plan_id=plan_id,
        file=file_path,
        before_hash=before_hash,
        after_hash=after_hash,
        parse_valid=parse_valid,
        invariants_met=invariants_met,
        estimated_risk=estimated_risk,
        duration_ms=duration_ms,
        timestamp=timestamp,
        policy_hash=policy_hash,
    )


def verify_receipt(receipt: Receipt, current_content: str) -> bool:
    """
    Verify that a file's current content matches the receipt's after_hash.

    Args:
        receipt: Receipt to verify
        current_content: Current file content

    Returns:
        True if current content matches receipt's after_hash

    Examples:
        >>> receipt = create_receipt("p1", "f.py", "old", "new", True, True, 0.1, 50)
        >>> verify_receipt(receipt, "new")
        True
        >>> verify_receipt(receipt, "modified")
        False
    """
    current_hash_full = content_hash(current_content)
    # Strip "sha256:" prefix if present to match receipt format
    current_hash = current_hash_full.replace("sha256:", "") if current_hash_full.startswith("sha256:") else current_hash_full
    return current_hash == receipt.after_hash


def is_idempotent_transformation(
    before_content: str, after_content: str
) -> bool:
    """
    Check if transformation was idempotent (no actual changes).

    Args:
        before_content: Content before transformation
        after_content: Content after transformation

    Returns:
        True if hashes match (no changes)

    Examples:
        >>> is_idempotent_transformation("x = 1", "x = 1")
        True
        >>> is_idempotent_transformation("x = 1", "x = 2")
        False
    """
    before_hash = content_hash(before_content)
    after_hash = content_hash(after_content)
    return before_hash == after_hash


def verify_receipts(base_path) -> list[str]:
    """
    Verify all receipts against journal and filesystem.

    Cross-checks that:
    1. Files mentioned in receipts still exist
    2. Current file hashes match receipt after_hash
    3. Receipts are consistent with journal entries

    Args:
        base_path: Base path for verification (Path or str)

    Returns:
        List of failure messages (empty if all OK)
    """
    from pathlib import Path
    import json

    base_path = Path(base_path)
    journals_dir = base_path / ".ace" / "journals"

    failures = []

    if not journals_dir.exists():
        return failures  # No journals, nothing to verify

    # Read all journal files
    for journal_file in sorted(journals_dir.glob("*.jsonl")):
        try:
            with open(journal_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        event_type = entry.get("event")

                        # Look for success events with receipts
                        if event_type == "success" and "receipt" in entry:
                            receipt_dict = entry["receipt"]
                            receipt = Receipt.from_dict(receipt_dict)

                            # Verify file exists
                            file_path = base_path / receipt.file
                            if not file_path.exists():
                                failures.append(
                                    f"{journal_file.name}:{line_no} - "
                                    f"File no longer exists: {receipt.file}"
                                )
                                continue

                            # Verify current content matches after_hash
                            try:
                                current_content = file_path.read_text(encoding="utf-8")
                                if not verify_receipt(receipt, current_content):
                                    failures.append(
                                        f"{journal_file.name}:{line_no} - "
                                        f"Hash mismatch for {receipt.file} "
                                        f"(expected {receipt.after_hash[:8]}...)"
                                    )
                            except Exception as e:
                                failures.append(
                                    f"{journal_file.name}:{line_no} - "
                                    f"Cannot read {receipt.file}: {e}"
                                )

                    except json.JSONDecodeError:
                        failures.append(
                            f"{journal_file.name}:{line_no} - Invalid JSON"
                        )

        except Exception as e:
            failures.append(f"{journal_file.name} - Cannot read journal: {e}")

    return failures
