"""Unified Issue Representation (UIR) scaffolding for ACE.

TODO: Define the full UIR schema and validation logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Finding:
    """Placeholder for ACE findings."""

    identifier: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Edit:
    """Placeholder for an atomic edit description."""

    location: str | None = None
    replacement: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EditPlan:
    """Placeholder for grouping edits associated with a finding."""

    finding_id: str | None = None
    edits: list[Edit] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Receipt:
    """Placeholder for execution receipts."""

    plan_id: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
