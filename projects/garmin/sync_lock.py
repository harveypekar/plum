"""Shared fcntl-based lock so cron and manual sync triggers never overlap."""
import fcntl
from contextlib import contextmanager
from pathlib import Path


class LockHeldError(Exception):
    """Raised when the sync lock is already held by another process."""


@contextmanager
def sync_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        fd.close()
        raise LockHeldError(f"Sync already in progress (lock held: {lock_path})") from e
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
