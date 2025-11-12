"""Session logging - Track analysis and apply sessions with stats."""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SessionLog:
    """Session log entry with timing and statistics."""

    session_id: str
    command: str
    started_at: str
    ended_at: str | None = None
    duration_seconds: float = 0.0
    target_path: str = ""
    rules_applied: list[str] = field(default_factory=list)
    files_analyzed: int = 0
    files_modified: int = 0
    findings_count: int = 0
    plans_count: int = 0
    reverted_count: int = 0
    success: bool = True
    error_message: str | None = None
    rule_stats: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "command": self.command,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "target_path": self.target_path,
            "rules_applied": self.rules_applied,
            "files_analyzed": self.files_analyzed,
            "files_modified": self.files_modified,
            "findings_count": self.findings_count,
            "plans_count": self.plans_count,
            "reverted_count": self.reverted_count,
            "success": self.success,
            "error_message": self.error_message,
            "rule_stats": self.rule_stats,
        }


class SessionLogger:
    """
    Session logger for tracking ACE operations.

    Logs to .ace/session.log in append-only JSONL format.
    """

    def __init__(self, log_path: Path | str = ".ace/session.log"):
        """
        Initialize session logger.

        Args:
            log_path: Path to session log file
        """
        self.log_path = Path(log_path)
        self.current_session: SessionLog | None = None
        self.start_time: float = 0.0

    def start_session(
        self,
        session_id: str,
        command: str,
        target_path: str = "",
        rules: list[str] | None = None,
    ) -> None:
        """
        Start a new session.

        Args:
            session_id: Unique session identifier
            command: Command being executed (analyze, apply, etc.)
            target_path: Target path being processed
            rules: List of rules being applied
        """
        self.start_time = time.time()

        self.current_session = SessionLog(
            session_id=session_id,
            command=command,
            started_at=datetime.now(timezone.utc).isoformat(),
            target_path=target_path,
            rules_applied=rules or [],
        )

    def update_stats(
        self,
        files_analyzed: int = 0,
        files_modified: int = 0,
        findings_count: int = 0,
        plans_count: int = 0,
        reverted_count: int = 0,
        rule_stats: dict[str, int] | None = None,
    ) -> None:
        """
        Update session statistics.

        Args:
            files_analyzed: Number of files analyzed
            files_modified: Number of files modified
            findings_count: Number of findings detected
            plans_count: Number of refactoring plans created
            reverted_count: Number of auto-reverted changes
            rule_stats: Per-rule statistics (rule_id -> count)
        """
        if self.current_session is None:
            return

        self.current_session.files_analyzed = files_analyzed
        self.current_session.files_modified = files_modified
        self.current_session.findings_count = findings_count
        self.current_session.plans_count = plans_count
        self.current_session.reverted_count = reverted_count

        if rule_stats:
            self.current_session.rule_stats = rule_stats

    def end_session(
        self,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """
        End the current session and write to log.

        Args:
            success: Whether the session completed successfully
            error_message: Optional error message if failed
        """
        if self.current_session is None:
            return

        end_time = time.time()
        duration = end_time - self.start_time

        self.current_session.ended_at = datetime.now(timezone.utc).isoformat()
        self.current_session.duration_seconds = duration
        self.current_session.success = success
        self.current_session.error_message = error_message

        # Write to log
        self._append_to_log(self.current_session)

        # Clear current session
        self.current_session = None

    def _append_to_log(self, session: SessionLog) -> None:
        """Append session to log file."""
        # Ensure directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append as JSONL
        with open(self.log_path, "a", encoding="utf-8") as f:
            line = json.dumps(session.to_dict(), separators=(",", ":"), sort_keys=True)
            f.write(line + "\n")

    def get_summary(self) -> str:
        """
        Get a human-readable summary of the current session.

        Returns:
            Summary string
        """
        if self.current_session is None:
            return "No active session"

        s = self.current_session
        summary = []
        summary.append(f"Session: {s.session_id}")
        summary.append(f"Command: {s.command}")
        summary.append(f"Target: {s.target_path}")

        if s.rules_applied:
            summary.append(f"Rules: {', '.join(s.rules_applied)}")

        if s.files_analyzed > 0:
            summary.append(f"Files analyzed: {s.files_analyzed}")
        if s.files_modified > 0:
            summary.append(f"Files modified: {s.files_modified}")
        if s.findings_count > 0:
            summary.append(f"Findings: {s.findings_count}")
        if s.plans_count > 0:
            summary.append(f"Plans: {s.plans_count}")
        if s.reverted_count > 0:
            summary.append(f"Auto-reverted: {s.reverted_count}")

        # Rule breakdown
        if s.rule_stats:
            summary.append("\nRule breakdown:")
            for rule_id, count in sorted(s.rule_stats.items()):
                summary.append(f"  {rule_id}: {count}")

        return "\n".join(summary)
