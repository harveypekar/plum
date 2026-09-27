"""Tests for the fcntl-based sync lock helper."""
import fcntl

import pytest

from sync_lock import LockHeldError, sync_lock


def test_sync_lock_allows_single_holder(tmp_path):
    lock_path = tmp_path / ".sync.lock"
    with sync_lock(lock_path):
        assert lock_path.exists()


def test_sync_lock_raises_when_already_held(tmp_path):
    lock_path = tmp_path / ".sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(LockHeldError):
            with sync_lock(lock_path):
                pass  # pragma: no cover - must not be reached
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def test_sync_lock_releases_after_use(tmp_path):
    lock_path = tmp_path / ".sync.lock"
    with sync_lock(lock_path):
        pass
    # Lock released on exit: a second acquisition must succeed immediately,
    # not block or raise.
    with sync_lock(lock_path):
        pass
