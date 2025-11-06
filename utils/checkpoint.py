"""Checkpoint utility for backup and restore operations"""
import shutil
from pathlib import Path


def checkpoint(src_dir: str, dest: str = ".checkpoints/LATEST") -> None:
    """
    Create a checkpoint by copying source directory tree.

    Args:
        src_dir: Source directory to backup
        dest: Destination checkpoint path (default: .checkpoints/LATEST)
    """
    src_path = Path(src_dir)
    dest_path = Path(dest)

    if not src_path.exists():
        raise ValueError(f"Source directory does not exist: {src_dir}")

    # Remove existing checkpoint if present
    if dest_path.exists():
        shutil.rmtree(dest_path)

    # Create parent directory if needed
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy entire tree
    shutil.copytree(src_path, dest_path)


def restore(checkpoint_path: str = ".checkpoints/LATEST", to_path: str = ".") -> None:
    """
    Restore from a checkpoint.

    Args:
        checkpoint_path: Path to checkpoint to restore from (default: .checkpoints/LATEST)
        to_path: Destination path to restore to (default: .)
    """
    src_path = Path(checkpoint_path)
    dest_path = Path(to_path)

    if not src_path.exists():
        raise ValueError(f"Checkpoint does not exist: {checkpoint_path}")

    # For safety, only restore if destination exists
    if not dest_path.exists():
        raise ValueError(f"Destination path does not exist: {to_path}")

    # Get the directory name from the checkpoint
    # If checkpoint is .checkpoints/LATEST/sample_project, we want to restore to ./sample_project
    for item in src_path.iterdir():
        target = dest_path / item.name

        # Remove existing item if present
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

        # Copy from checkpoint
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
