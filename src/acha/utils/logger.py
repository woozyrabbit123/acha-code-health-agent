"""JSONL session logger for structured output."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class JSONLLogger:
    """Append-only JSONL logger with simple size-based rotation."""
    def __init__(self, log_path: Path, max_size_mb: float = 1.0):
        self.log_path = log_path
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed()

    def _rotate_if_needed(self) -> None:
        if self.log_path.exists() and self.log_path.stat().st_size > self.max_size_bytes:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            rotated = self.log_path.with_suffix(f".{ts}.jsonl")
            self.log_path.rename(rotated)

    def log(self, event_type: str, data: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            **data,
        }
        # append atomically-ish
        with self.log_path.open("a", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")

    def close(self) -> None:
        self.log("session_end", {"status": "complete"})


# Global singleton
_session_logger: Optional[JSONLLogger] = None

def init_session_logger(path: Path = Path("reports/session.jsonl")) -> None:
    global _session_logger
    _session_logger = JSONLLogger(path)
    _session_logger.log("session_start", {"version": "0.2.0"})

def log_event(event_type: str, data: Dict[str, Any]) -> None:
    if _session_logger:
        _session_logger.log(event_type, data)

def close_session_logger() -> None:
    global _session_logger
    if _session_logger:
        _session_logger.close()
        _session_logger = None
