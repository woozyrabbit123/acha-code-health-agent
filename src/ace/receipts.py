"""Receipt generation for tracking refactoring applications.

Receipts provide cryptographic proof and validation records of code transformations.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone

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

    def to_dict(self) -> dict:
        """Convert receipt to dictionary for JSON serialization."""
        return {
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
    timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

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
