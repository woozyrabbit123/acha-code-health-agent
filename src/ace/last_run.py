"""ACE last run tracking for repeat command."""

import hashlib
import json
import time
from pathlib import Path

from ace import __version__


def save(argv: list[str], cache_dir: str = ".ace") -> None:
    """
    Save last run command to cache.

    Args:
        argv: Command line arguments
        cache_dir: Cache directory (default: .ace)
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    last_run_path = cache_path / "last_run.json"

    # Compute hash of argv
    argv_str = " ".join(argv)
    argv_hash = hashlib.sha256(argv_str.encode("utf-8")).hexdigest()

    data = {
        "argv": argv,
        "version": __version__,
        "hash": argv_hash,
        "timestamp": time.time(),
    }

    last_run_path.write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )


def load(cache_dir: str = ".ace") -> list[str] | None:
    """
    Load last run command from cache.

    Args:
        cache_dir: Cache directory (default: .ace)

    Returns:
        Command line arguments if available, None otherwise
    """
    last_run_path = Path(cache_dir) / "last_run.json"

    if not last_run_path.exists():
        return None

    try:
        content = last_run_path.read_text(encoding="utf-8")
        data = json.loads(content)

        # Verify hash
        argv = data.get("argv", [])
        stored_hash = data.get("hash", "")
        computed_hash = hashlib.sha256(" ".join(argv).encode("utf-8")).hexdigest()

        if stored_hash != computed_hash:
            # Hash mismatch - corrupted data
            return None

        return argv

    except Exception:
        # If we can't read or parse the file, return None
        return None
