# Google Incremental Backup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automated incremental backup of Gmail, Calendar, Contacts, Drive, Tasks, and YouTube to the local filesystem using Google APIs.

**Architecture:** Python package at `scripts/backup/google-backup/` with modular service plugins. Bash wrapper for cron. JSON state files for incremental sync. One file per backed-up item.

**Tech Stack:** Python 3.10+, google-api-python-client, google-auth-oauthlib, bash (run.sh wrapper), existing Plum logging/env utilities.

**Spec:** `docs/superpowers/specs/2026-03-23-google-incremental-backup-design.md`

**Worktree:** `cd /mnt/d/prg/plum-google-backup && git switch google-backup-spec`

---

### Task 1: Project scaffolding and env variables

**Files:**
- Create: `scripts/backup/google-backup/requirements.txt`
- Create: `scripts/backup/google-backup/google_backup/__init__.py`
- Create: `scripts/backup/google-backup/google_backup/services/__init__.py`
- Modify: `.env.example:17` (after existing variables)

- [ ] **Step 1: Create the directory structure**

```bash
cd /mnt/d/prg/plum-google-backup
mkdir -p scripts/backup/google-backup/google_backup/services
```

- [ ] **Step 2: Create requirements.txt**

```
# scripts/backup/google-backup/requirements.txt
google-api-python-client>=2.100.0
google-auth-oauthlib>=1.1.0
google-auth-httplib2>=0.2.0
```

- [ ] **Step 3: Create google_backup/__init__.py**

```python
"""Google account incremental backup tool."""
```

- [ ] **Step 4: Create google_backup/services/__init__.py**

```python
"""Service registry — discovers and exposes all backup service modules."""

from google_backup.services.base import BaseService, SyncResult

# Registry populated by import side-effects; each service module appends itself.
_registry: dict[str, type[BaseService]] = {}


def register(cls: type[BaseService]) -> type[BaseService]:
    """Decorator: register a service class by its name."""
    _registry[cls.name] = cls
    return cls


def get_all() -> dict[str, type[BaseService]]:
    """Return all registered services. Imports modules to trigger registration."""
    # Import each service module so @register decorators fire.
    from google_backup.services import (  # noqa: F401
        calendar,
        contacts,
        drive,
        gmail,
        tasks,
        youtube,
    )
    return dict(_registry)


def get(name: str) -> type[BaseService]:
    """Return a single registered service by name."""
    all_services = get_all()
    if name not in all_services:
        raise KeyError(f"Unknown service: {name}. Available: {', '.join(all_services)}")
    return all_services[name]
```

- [ ] **Step 5: Add env variables to .env.example**

Add after the existing `LOGS_DIR` line:

```bash
# Google Backup
GOOGLE_BACKUP_CLIENT_SECRET=
GOOGLE_BACKUP_DIR=
GOOGLE_BACKUP_MAX_DISK_GB=
```

- [ ] **Step 6: Commit**

```bash
git add scripts/backup/google-backup/requirements.txt \
       scripts/backup/google-backup/google_backup/__init__.py \
       scripts/backup/google-backup/google_backup/services/__init__.py \
       .env.example
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): scaffold google-backup package and env variables"
```

---

### Task 2: Base service interface and SyncResult

**Files:**
- Create: `scripts/backup/google-backup/google_backup/services/base.py`
- Create: `scripts/backup/google-backup/tests/__init__.py`
- Create: `scripts/backup/google-backup/tests/test_base.py`

- [ ] **Step 1: Write the test for SyncResult**

```python
# scripts/backup/google-backup/tests/test_base.py
"""Tests for base service interface."""
from google_backup.services.base import SyncResult


def test_sync_result_has_errors_when_items_failed():
    result = SyncResult(
        service="test",
        items_synced=10,
        items_failed=2,
        items_deleted=0,
        failed_ids=["a", "b"],
        elapsed_seconds=1.5,
    )
    assert result.has_errors is True


def test_sync_result_no_errors_when_all_succeed():
    result = SyncResult(
        service="test",
        items_synced=10,
        items_failed=0,
        items_deleted=0,
        failed_ids=[],
        elapsed_seconds=1.0,
    )
    assert result.has_errors is False


def test_sync_result_summary_format():
    result = SyncResult(
        service="gmail",
        items_synced=100,
        items_failed=3,
        items_deleted=5,
        failed_ids=["x", "y", "z"],
        elapsed_seconds=12.34,
    )
    summary = result.summary()
    assert "gmail" in summary
    assert "100" in summary
    assert "3 failed" in summary
    assert "5 deleted" in summary
```

- [ ] **Step 2: Create empty tests/__init__.py**

```python
# scripts/backup/google-backup/tests/__init__.py
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_base.py -v
```

Expected: ImportError — `google_backup.services.base` does not exist yet.

- [ ] **Step 4: Implement base.py**

```python
# scripts/backup/google-backup/google_backup/services/base.py
"""Abstract base class for all backup services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
    from google_backup.state import ServiceState


@dataclass
class SyncResult:
    """Summary of a sync operation."""

    service: str
    items_synced: int
    items_failed: int
    items_deleted: int
    failed_ids: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def has_errors(self) -> bool:
        return self.items_failed > 0

    def summary(self) -> str:
        parts = [
            f"[{self.service}]",
            f"{self.items_synced} synced",
        ]
        if self.items_failed:
            parts.append(f"{self.items_failed} failed (IDs: {', '.join(self.failed_ids)})")
        if self.items_deleted:
            parts.append(f"{self.items_deleted} deleted")
        parts.append(f"in {self.elapsed_seconds:.1f}s")
        return " | ".join(parts)


class BaseService(ABC):
    """Abstract base for a Google backup service."""

    name: str = ""
    scopes: tuple[str, ...] = ()

    @abstractmethod
    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        """Run incremental sync. Mutates state with sync tokens. Returns summary."""
        ...
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_base.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/backup/google-backup/google_backup/services/base.py \
       scripts/backup/google-backup/tests/__init__.py \
       scripts/backup/google-backup/tests/test_base.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add BaseService interface and SyncResult dataclass"
```

---

### Task 3: State management

**Files:**
- Create: `scripts/backup/google-backup/google_backup/state.py`
- Create: `scripts/backup/google-backup/tests/test_state.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_state.py
"""Tests for sync state management."""
import json

from google_backup.state import ServiceState


def test_load_returns_empty_for_missing_file(tmp_path):
    state = ServiceState.load(tmp_path / "state", "gmail")
    assert state.data == {}
    assert state.service == "gmail"


def test_save_and_load_roundtrip(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")
    state.data["history_id"] = "12345"
    state.save()

    reloaded = ServiceState.load(state_dir, "gmail")
    assert reloaded.data["history_id"] == "12345"


def test_save_writes_last_run(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")
    state.save()

    raw = json.loads((state_dir / "gmail.json").read_text())
    assert "last_run" in raw


def test_partial_cursor_lifecycle(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")

    # Set partial cursor during long sync
    state.set_partial_cursor("page_token_abc")
    assert state.get_partial_cursor() == "page_token_abc"

    # Clear on successful completion
    state.clear_partial_cursor()
    assert state.get_partial_cursor() is None

    # Partial cursor persists across loads (for crash recovery)
    state2 = ServiceState.load(state_dir, "gmail")
    state2.set_partial_cursor("page_token_xyz")
    # Not calling save() here — set_partial_cursor writes immediately
    state3 = ServiceState.load(state_dir, "gmail")
    assert state3.get_partial_cursor() == "page_token_xyz"


def test_status_report(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")
    state.data["history_id"] = "99999"
    state.data["items_backed_up"] = 5000
    state.save()

    reloaded = ServiceState.load(state_dir, "gmail")
    report = reloaded.status()
    assert "gmail" in report
    assert "99999" in report or "5000" in report
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_state.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement state.py**

```python
# scripts/backup/google-backup/google_backup/state.py
"""Per-service sync state, persisted as JSON files."""

import json
from datetime import datetime, timezone
from pathlib import Path


class ServiceState:
    """Read/write sync state for a single service."""

    def __init__(self, state_dir: Path, service: str, data: dict):
        self.state_dir = state_dir
        self.service = service
        self.data = data
        self._path = state_dir / f"{service}.json"

    @classmethod
    def load(cls, state_dir: Path, service: str) -> "ServiceState":
        """Load state from disk, or return empty state if not found."""
        path = state_dir / f"{service}.json"
        if path.exists():
            data = json.loads(path.read_text())
        else:
            data = {}
        return cls(state_dir, service, data)

    def save(self) -> None:
        """Write state to disk with updated last_run timestamp."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.data["last_run"] = datetime.now(timezone.utc).isoformat()
        self._path.write_text(json.dumps(self.data, indent=2) + "\n")

    def set_partial_cursor(self, cursor: str) -> None:
        """Write a partial cursor immediately (crash recovery for long syncs)."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.data["partial_cursor"] = cursor
        self._path.write_text(json.dumps(self.data, indent=2) + "\n")

    def get_partial_cursor(self) -> str | None:
        """Get partial cursor if one exists, else None."""
        return self.data.get("partial_cursor")

    def clear_partial_cursor(self) -> None:
        """Remove partial cursor (called on successful sync completion)."""
        self.data.pop("partial_cursor", None)

    def status(self) -> str:
        """Human-readable status report."""
        if not self.data:
            return f"[{self.service}] Never synced"
        last_run = self.data.get("last_run", "unknown")
        items = self.data.get("items_backed_up", "?")
        details = {k: v for k, v in self.data.items()
                   if k not in ("last_run", "items_backed_up", "partial_cursor")}
        parts = [f"[{self.service}] Last run: {last_run} | Items: {items}"]
        if details:
            parts.append(f"State: {json.dumps(details)}")
        cursor = self.get_partial_cursor()
        if cursor:
            parts.append(f"WARNING: Incomplete sync (cursor: {cursor})")
        return " | ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_state.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/state.py \
       scripts/backup/google-backup/tests/test_state.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add sync state management with partial cursor support"
```

---

### Task 4: Auth module

**Files:**
- Create: `scripts/backup/google-backup/google_backup/auth.py`
- Create: `scripts/backup/google-backup/tests/test_auth.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_auth.py
"""Tests for OAuth2 auth module."""
import json
from unittest.mock import patch, MagicMock

from google_backup.auth import AuthManager


def test_all_scopes_are_readonly():
    manager = AuthManager.__new__(AuthManager)
    for scope in AuthManager.SCOPES:
        assert "readonly" in scope, f"Scope is not read-only: {scope}"


def test_all_scopes_use_full_uri():
    for scope in AuthManager.SCOPES:
        assert scope.startswith("https://"), f"Scope must use full URI: {scope}"


def test_token_path(tmp_path):
    manager = AuthManager(
        client_secret_path=tmp_path / "secret.json",
        state_dir=tmp_path / "state",
    )
    assert manager.token_path == tmp_path / "state" / "token.json"


def test_is_authorized_false_when_no_token(tmp_path):
    manager = AuthManager(
        client_secret_path=tmp_path / "secret.json",
        state_dir=tmp_path / "state",
    )
    assert manager.is_authorized() is False


def test_is_authorized_true_when_valid_token_exists(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    # Write a minimal token file
    token_data = {
        "token": "access_token_123",
        "refresh_token": "refresh_token_456",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "test_secret",
        "scopes": AuthManager.SCOPES,
    }
    (state_dir / "token.json").write_text(json.dumps(token_data))

    manager = AuthManager(
        client_secret_path=tmp_path / "secret.json",
        state_dir=state_dir,
    )
    assert manager.is_authorized() is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_auth.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement auth.py**

```python
# scripts/backup/google-backup/google_backup/auth.py
"""OAuth2 authentication for Google APIs."""

import json
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

log = logging.getLogger(__name__)

# All read-only — the backup never modifies anything in the Google account.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class AuthManager:
    """Handles OAuth2 flow and credential storage."""

    SCOPES = SCOPES

    def __init__(self, client_secret_path: Path, state_dir: Path):
        self.client_secret_path = Path(client_secret_path)
        self.state_dir = Path(state_dir)
        self.token_path = self.state_dir / "token.json"

    def is_authorized(self) -> bool:
        """Check if a valid (or refreshable) token exists."""
        return self.token_path.exists()

    def authorize_interactive(self) -> Credentials:
        """Run the browser-based OAuth2 flow. Saves token to disk."""
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"Client secret not found at {self.client_secret_path}. "
                "Download it from Google Cloud Console and set GOOGLE_BACKUP_CLIENT_SECRET in .env"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secret_path),
            scopes=self.SCOPES,
        )
        creds = flow.run_local_server(port=0)
        self._save_token(creds)
        log.info("Authorization successful. Token saved to %s", self.token_path)
        return creds

    def get_credentials(self) -> Credentials:
        """Load credentials from disk, refreshing if needed."""
        if not self.token_path.exists():
            raise RuntimeError(
                "Not authorized. Run 'run.sh auth' first to complete the OAuth2 flow."
            )

        creds = Credentials.from_authorized_user_file(
            str(self.token_path), scopes=self.SCOPES
        )

        if creds.expired and creds.refresh_token:
            log.info("Access token expired, refreshing...")
            try:
                creds.refresh(Request())
                self._save_token(creds)
                log.info("Token refreshed successfully")
            except Exception as e:
                raise RuntimeError(
                    f"Token refresh failed: {e}. Re-run 'run.sh auth' to re-authorize."
                ) from e

        return creds

    def _save_token(self, creds: Credentials) -> None:
        """Persist credentials to disk."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_auth.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/auth.py \
       scripts/backup/google-backup/tests/test_auth.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add OAuth2 auth manager with token persistence"
```

---

### Task 5: CLI entry point

**Files:**
- Create: `scripts/backup/google-backup/google_backup/__main__.py`
- Create: `scripts/backup/google-backup/tests/test_cli.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_cli.py
"""Tests for CLI argument parsing and dispatch."""
from unittest.mock import patch, MagicMock
from google_backup.__main__ import parse_args


def test_parse_all_flag():
    args = parse_args(["--all"])
    assert args.all is True


def test_parse_individual_services():
    args = parse_args(["--gmail", "--contacts"])
    assert args.gmail is True
    assert args.contacts is True
    assert args.calendar is False


def test_parse_status_flag():
    args = parse_args(["--status"])
    assert args.status is True


def test_parse_auth_command():
    args = parse_args(["auth"])
    assert args.command == "auth"


def test_default_is_sync_command():
    args = parse_args(["--all"])
    assert args.command == "sync"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_cli.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement __main__.py**

```python
# scripts/backup/google-backup/google_backup/__main__.py
"""CLI entry point: python -m google_backup [auth|--all|--gmail|...]."""

import argparse
import logging
import os
import sys
from pathlib import Path

from google_backup.auth import AuthManager
from google_backup.services import get_all
from google_backup.state import ServiceState

log = logging.getLogger("google_backup")

SERVICE_NAMES = ["gmail", "calendar", "contacts", "drive", "tasks", "youtube"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="google-backup",
        description="Incremental backup of Google account data.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("auth", help="Run OAuth2 authorization flow (opens browser)")

    # Default command is "sync" (no subcommand needed)
    parser.set_defaults(command="sync")

    parser.add_argument("--all", action="store_true", help="Backup all services")
    parser.add_argument("--status", action="store_true", help="Show sync status and exit")
    for name in SERVICE_NAMES:
        parser.add_argument(f"--{name}", action="store_true", help=f"Backup {name}")

    return parser.parse_args(argv)


def setup_logging() -> None:
    """Configure Python logging to write to LOG_FILE (from bash wrapper) and console."""
    log.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    log.addHandler(console)

    log_file = os.environ.get("LOG_FILE")
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(fh)


def get_config() -> tuple[Path, Path]:
    """Read config from env variables. Returns (client_secret_path, backup_dir)."""
    client_secret = os.environ.get("GOOGLE_BACKUP_CLIENT_SECRET")
    if not client_secret:
        log.error("GOOGLE_BACKUP_CLIENT_SECRET not set in .env")
        sys.exit(1)

    backup_dir = os.environ.get("GOOGLE_BACKUP_DIR")
    if not backup_dir:
        log.error("GOOGLE_BACKUP_DIR not set in .env")
        sys.exit(1)

    return Path(client_secret).expanduser(), Path(backup_dir).expanduser()


def resolve_services(args: argparse.Namespace) -> list[str]:
    """Determine which services to run based on CLI args."""
    if args.all:
        return SERVICE_NAMES
    selected = [name for name in SERVICE_NAMES if getattr(args, name, False)]
    if not selected:
        log.error("No services selected. Use --all or --gmail, --calendar, etc.")
        sys.exit(1)
    return selected


def cmd_status(backup_dir: Path) -> None:
    """Print sync status for all services and exit."""
    state_dir = backup_dir / "state"
    for name in SERVICE_NAMES:
        state = ServiceState.load(state_dir, name)
        print(state.status())


def cmd_auth(client_secret: Path, backup_dir: Path) -> None:
    """Run interactive OAuth2 flow."""
    auth = AuthManager(client_secret, backup_dir / "state")
    auth.authorize_interactive()
    print("Authorization complete.")


def cmd_sync(client_secret: Path, backup_dir: Path, service_names: list[str]) -> int:
    """Run sync for selected services. Returns exit code."""
    auth = AuthManager(client_secret, backup_dir / "state")
    creds = auth.get_credentials()
    state_dir = backup_dir / "state"

    registry = get_all()
    any_errors = False

    for name in service_names:
        if name not in registry:
            log.warning("Service '%s' not yet implemented, skipping", name)
            continue

        service_cls = registry[name]
        service = service_cls()
        state = ServiceState.load(state_dir, name)
        service_backup_dir = backup_dir / name

        log.info("Starting sync: %s", name)
        # Pass state INTO sync — service mutates it with sync tokens/historyIds
        result = service.sync(creds, state, service_backup_dir)
        log.info(result.summary())

        if result.has_errors:
            any_errors = True

        # Save state (with sync tokens set by service + updated item count)
        state.data["items_backed_up"] = result.items_synced
        state.clear_partial_cursor()
        state.save()

    return 1 if any_errors else 0


def main() -> None:
    setup_logging()
    args = parse_args()

    if args.command == "auth":
        client_secret, backup_dir = get_config()
        cmd_auth(client_secret, backup_dir)
        return

    if args.status:
        _, backup_dir = get_config()
        cmd_status(backup_dir)
        return

    client_secret, backup_dir = get_config()
    service_names = resolve_services(args)
    exit_code = cmd_sync(client_secret, backup_dir, service_names)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_cli.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/__main__.py \
       scripts/backup/google-backup/tests/test_cli.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add CLI entry point with arg parsing and dispatch"
```

---

### Task 6: Bash wrapper (run.sh)

**Files:**
- Create: `scripts/backup/google-backup/run.sh`

- [ ] **Step 1: Create run.sh**

```bash
#!/bin/bash
# Bash wrapper for google-backup: sources Plum env/logging, activates venv, runs Python.
# Usage: bash scripts/backup/google-backup/run.sh [auth|--all|--gmail|...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUM_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source Plum utilities
export SCRIPT_NAME="google-backup"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/logging.sh"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/load-env.sh"

log_info "google-backup starting with args: $*"

# Activate venv (create if missing)
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    pip install -q -r "$SCRIPT_DIR/requirements.txt"
else
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi

# Pass LOG_FILE to Python (set by logging.sh)
export LOG_FILE

# Set PYTHONPATH so python -m google_backup finds the package
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

# Run the Python package, forwarding all args
python -m google_backup "$@"
EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
    log_info "google-backup completed successfully"
else
    log_error "google-backup exited with code $EXIT_CODE"
fi

exit "$EXIT_CODE"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/backup/google-backup/run.sh
```

- [ ] **Step 3: Run shellcheck**

```bash
shellcheck scripts/backup/google-backup/run.sh
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add scripts/backup/google-backup/run.sh
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add bash wrapper for google-backup"
```

---

### Task 7: Tasks service (simplest — full dump)

**Files:**
- Create: `scripts/backup/google-backup/google_backup/services/tasks.py`
- Create: `scripts/backup/google-backup/tests/test_tasks.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_tasks.py
"""Tests for Google Tasks backup service."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from google_backup.services.tasks import TasksService
from google_backup.services.base import SyncResult
from google_backup.state import ServiceState


def _mock_tasks_api(task_lists, tasks_by_list):
    """Build a mock Google Tasks API service."""
    service = MagicMock()

    # tasklists().list() + pagination termination
    service.tasklists.return_value.list.return_value.execute.return_value = {
        "items": task_lists,
    }
    service.tasklists.return_value.list_next.return_value = None

    def _tasks_list(tasklist, **kwargs):
        mock = MagicMock()
        mock.execute.return_value = {"items": tasks_by_list.get(tasklist, [])}
        return mock

    service.tasks.return_value.list.side_effect = _tasks_list
    service.tasks.return_value.list_next.return_value = None
    return service


def test_tasks_sync_creates_files(tmp_path):
    task_lists = [{"id": "list1", "title": "My Tasks"}]
    tasks_by_list = {
        "list1": [
            {"id": "task_a", "title": "Buy milk", "status": "needsAction"},
            {"id": "task_b", "title": "Call dentist", "status": "completed"},
        ],
    }

    mock_api = _mock_tasks_api(task_lists, tasks_by_list)
    state = ServiceState.load(tmp_path / "state", "tasks")
    backup_dir = tmp_path / "tasks"

    with patch("google_backup.services.tasks.build", return_value=mock_api):
        svc = TasksService()
        result = svc.sync(MagicMock(), state, backup_dir)

    assert result.items_synced == 2
    assert result.items_failed == 0
    assert (backup_dir / "list1" / "task_a.json").exists()
    assert (backup_dir / "list1" / "task_b.json").exists()

    data = json.loads((backup_dir / "list1" / "task_a.json").read_text())
    assert data["title"] == "Buy milk"


def test_tasks_sync_removes_orphaned_files(tmp_path):
    """Tasks deleted on Google's side should be removed locally."""
    state = ServiceState.load(tmp_path / "state", "tasks")
    backup_dir = tmp_path / "tasks"

    # Pre-existing local file for a task that no longer exists
    (backup_dir / "list1").mkdir(parents=True)
    (backup_dir / "list1" / "task_old.json").write_text('{"id": "task_old"}')

    task_lists = [{"id": "list1", "title": "My Tasks"}]
    tasks_by_list = {
        "list1": [{"id": "task_new", "title": "New task", "status": "needsAction"}],
    }
    mock_api = _mock_tasks_api(task_lists, tasks_by_list)

    with patch("google_backup.services.tasks.build", return_value=mock_api):
        svc = TasksService()
        result = svc.sync(MagicMock(), state, backup_dir)

    assert result.items_synced == 1
    assert not (backup_dir / "list1" / "task_old.json").exists()
    assert (backup_dir / "list1" / "task_new.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_tasks.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement tasks.py**

```python
# scripts/backup/google-backup/google_backup/services/tasks.py
"""Google Tasks backup service — full dump each run."""

import json
import logging
import time
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from google_backup.services import register
from google_backup.services.base import BaseService, SyncResult
from google_backup.state import ServiceState

log = logging.getLogger(__name__)


@register
class TasksService(BaseService):
    name = "tasks"
    scopes = ("https://www.googleapis.com/auth/tasks.readonly",)

    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        start = time.time()
        service = build("tasks", "v1", credentials=creds)
        items_synced = 0
        items_failed = 0
        items_deleted = 0
        failed_ids: list[str] = []

        # Get all task lists (paginated)
        task_lists: list[dict] = []
        request = service.tasklists().list(maxResults=100)
        while request:
            response = request.execute()
            task_lists.extend(response.get("items", []))
            request = service.tasklists().list_next(request, response)

        # Track all current task IDs per list for orphan cleanup
        current_ids: dict[str, set[str]] = {}

        for tl in task_lists:
            list_id = tl["id"]
            list_dir = backup_dir / list_id
            list_dir.mkdir(parents=True, exist_ok=True)
            current_ids[list_id] = set()

            try:
                # Paginate tasks within list
                tasks: list[dict] = []
                req = service.tasks().list(tasklist=list_id, maxResults=100)
                while req:
                    resp = req.execute()
                    tasks.extend(resp.get("items", []))
                    req = service.tasks().list_next(req, resp)
            except Exception as e:
                log.error("Failed to fetch tasks for list %s: %s", list_id, e)
                items_failed += 1
                failed_ids.append(f"list:{list_id}")
                continue

            for task in tasks:
                task_id = task["id"]
                current_ids[list_id].add(task_id)
                try:
                    (list_dir / f"{task_id}.json").write_text(
                        json.dumps(task, indent=2, ensure_ascii=False) + "\n"
                    )
                    items_synced += 1
                except Exception as e:
                    log.error("Failed to write task %s: %s", task_id, e)
                    items_failed += 1
                    failed_ids.append(task_id)

            # Remove orphaned task files
            for existing_file in list_dir.glob("*.json"):
                task_id = existing_file.stem
                if task_id not in current_ids[list_id]:
                    log.info("Removing orphaned task: %s/%s", list_id, task_id)
                    existing_file.unlink()
                    items_deleted += 1

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=items_deleted,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_tasks.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/services/tasks.py \
       scripts/backup/google-backup/tests/test_tasks.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add Tasks service with orphan cleanup"
```

---

### Task 8: YouTube service (full dump with diff logging)

**Files:**
- Create: `scripts/backup/google-backup/google_backup/services/youtube.py`
- Create: `scripts/backup/google-backup/tests/test_youtube.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_youtube.py
"""Tests for YouTube backup service."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from google_backup.services.youtube import YouTubeService
from google_backup.state import ServiceState


def _mock_youtube_api(subscriptions, playlists, playlist_items, liked_videos):
    """Build a mock YouTube API service."""
    service = MagicMock()

    # subscriptions().list() + pagination on resource
    sub_mock = MagicMock()
    sub_mock.execute.return_value = {"items": subscriptions}
    service.subscriptions.return_value.list.return_value = sub_mock
    service.subscriptions.return_value.list_next.return_value = None

    # playlists().list() + pagination on resource
    pl_mock = MagicMock()
    pl_mock.execute.return_value = {"items": playlists}
    service.playlists.return_value.list.return_value = pl_mock
    service.playlists.return_value.list_next.return_value = None

    # playlistItems().list() + pagination on resource
    def _playlist_items(playlistId, **kwargs):
        mock = MagicMock()
        mock.execute.return_value = {"items": playlist_items.get(playlistId, [])}
        return mock
    service.playlistItems.return_value.list.side_effect = _playlist_items
    service.playlistItems.return_value.list_next.return_value = None

    # videos().list() + pagination on resource
    vid_mock = MagicMock()
    vid_mock.execute.return_value = {"items": liked_videos}
    service.videos.return_value.list.return_value = vid_mock
    service.videos.return_value.list_next.return_value = None

    return service


def test_youtube_sync_creates_files(tmp_path):
    subs = [{"snippet": {"resourceId": {"channelId": "UC1"}, "title": "Channel One"}}]
    playlists = [{"id": "PL1", "snippet": {"title": "Favorites"}}]
    playlist_items = {"PL1": [{"snippet": {"resourceId": {"videoId": "vid1"}}}]}
    liked = [{"id": "vid2", "snippet": {"title": "Cool Video"}}]

    mock_api = _mock_youtube_api(subs, playlists, playlist_items, liked)
    state = ServiceState.load(tmp_path / "state", "youtube")

    with patch("google_backup.services.youtube.build", return_value=mock_api):
        svc = YouTubeService()
        result = svc.sync(MagicMock(), state, tmp_path / "youtube")

    assert result.items_synced > 0
    assert (tmp_path / "youtube" / "subscriptions.json").exists()
    assert (tmp_path / "youtube" / "liked_videos.json").exists()
    assert (tmp_path / "youtube" / "playlists" / "PL1.json").exists()


def test_youtube_logs_removed_subscriptions(tmp_path, caplog):
    """When a subscription disappears between runs, it should be logged."""
    backup_dir = tmp_path / "youtube"
    backup_dir.mkdir(parents=True)

    # Previous run had two subscriptions
    (backup_dir / "subscriptions.json").write_text(json.dumps([
        {"snippet": {"resourceId": {"channelId": "UC1"}, "title": "Channel One"}},
        {"snippet": {"resourceId": {"channelId": "UC2"}, "title": "Channel Two"}},
    ]))

    # Current run has only one
    subs = [{"snippet": {"resourceId": {"channelId": "UC1"}, "title": "Channel One"}}]
    mock_api = _mock_youtube_api(subs, [], {}, [])
    state = ServiceState.load(tmp_path / "state", "youtube")

    with patch("google_backup.services.youtube.build", return_value=mock_api):
        import logging
        with caplog.at_level(logging.INFO, logger="google_backup.services.youtube"):
            svc = YouTubeService()
            svc.sync(MagicMock(), state, backup_dir)

    assert any("Channel Two" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_youtube.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement youtube.py**

```python
# scripts/backup/google-backup/google_backup/services/youtube.py
"""YouTube backup service — full dump with diff logging."""

import json
import logging
import time
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from google_backup.services import register
from google_backup.services.base import BaseService, SyncResult
from google_backup.state import ServiceState

log = logging.getLogger(__name__)


def _paginate(resource, request):
    """Collect all pages from a YouTube API list request.

    Args:
        resource: The API resource (e.g., service.subscriptions()) — has list_next().
        request: The initial list request object.
    """
    items = []
    while request:
        response = request.execute()
        items.extend(response.get("items", []))
        request = resource.list_next(request, response)
    return items


def _diff_and_log(label: str, old_path: Path, new_items: list, key_fn):
    """Compare old file to new items and log removals."""
    if not old_path.exists():
        return
    try:
        old_items = json.loads(old_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    old_keys = {key_fn(item) for item in old_items}
    new_keys = {key_fn(item) for item in new_items}
    removed = old_keys - new_keys
    for key in removed:
        # Find the title from old items
        for item in old_items:
            if key_fn(item) == key:
                title = item.get("snippet", {}).get("title", key)
                log.info("%s removed: %s", label, title)
                break


@register
class YouTubeService(BaseService):
    name = "youtube"
    scopes = ("https://www.googleapis.com/auth/youtube.readonly",)

    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        start = time.time()
        service = build("youtube", "v3", credentials=creds)
        backup_dir.mkdir(parents=True, exist_ok=True)
        items_synced = 0
        items_failed = 0
        failed_ids: list[str] = []

        # --- Subscriptions ---
        try:
            sub_resource = service.subscriptions()
            subs = _paginate(sub_resource, sub_resource.list(part="snippet", mine=True, maxResults=50))
            _diff_and_log(
                "Subscription",
                backup_dir / "subscriptions.json",
                subs,
                lambda s: s["snippet"]["resourceId"]["channelId"],
            )
            (backup_dir / "subscriptions.json").write_text(
                json.dumps(subs, indent=2, ensure_ascii=False) + "\n"
            )
            items_synced += len(subs)
        except Exception as e:
            log.error("Failed to sync subscriptions: %s", e)
            items_failed += 1
            failed_ids.append("subscriptions")

        # --- Playlists ---
        try:
            pl_resource = service.playlists()
            playlists = _paginate(pl_resource, pl_resource.list(part="snippet,contentDetails", mine=True, maxResults=50))
            playlists_dir = backup_dir / "playlists"
            playlists_dir.mkdir(parents=True, exist_ok=True)

            for pl in playlists:
                pl_id = pl["id"]
                try:
                    pli_resource = service.playlistItems()
                    pl_items = _paginate(
                        pli_resource, pli_resource.list(playlistId=pl_id, part="snippet", maxResults=50)
                    )
                    pl["items"] = pl_items
                    (playlists_dir / f"{pl_id}.json").write_text(
                        json.dumps(pl, indent=2, ensure_ascii=False) + "\n"
                    )
                    items_synced += 1
                except Exception as e:
                    log.error("Failed to sync playlist %s: %s", pl_id, e)
                    items_failed += 1
                    failed_ids.append(f"playlist:{pl_id}")
        except Exception as e:
            log.error("Failed to list playlists: %s", e)
            items_failed += 1
            failed_ids.append("playlists")

        # --- Liked videos ---
        try:
            vid_resource = service.videos()
            liked = _paginate(vid_resource, vid_resource.list(part="snippet", myRating="like", maxResults=50))
            _diff_and_log(
                "Liked video",
                backup_dir / "liked_videos.json",
                liked,
                lambda v: v["id"],
            )
            (backup_dir / "liked_videos.json").write_text(
                json.dumps(liked, indent=2, ensure_ascii=False) + "\n"
            )
            items_synced += len(liked)
        except Exception as e:
            log.error("Failed to sync liked videos: %s", e)
            items_failed += 1
            failed_ids.append("liked_videos")

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=0,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_youtube.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/services/youtube.py \
       scripts/backup/google-backup/tests/test_youtube.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add YouTube service with removal diff logging"
```

---

### Task 9: Calendar service (syncToken incremental)

**Files:**
- Create: `scripts/backup/google-backup/google_backup/services/calendar.py`
- Create: `scripts/backup/google-backup/tests/test_calendar.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_calendar.py
"""Tests for Google Calendar backup service."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from google_backup.services.calendar import CalendarService
from google_backup.state import ServiceState


def _mock_calendar_api(calendars, events_by_calendar, next_sync_token="token_abc"):
    """Build a mock Google Calendar API service."""
    service = MagicMock()

    # calendarList().list()
    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": calendars,
    }

    # events().list() + pagination termination on resource
    def _events_list(calendarId, **kwargs):
        mock = MagicMock()
        mock.execute.return_value = {
            "items": events_by_calendar.get(calendarId, []),
            "nextSyncToken": next_sync_token,
        }
        return mock

    service.events.return_value.list.side_effect = _events_list
    service.events.return_value.list_next.return_value = None
    return service


def test_calendar_full_sync(tmp_path):
    calendars = [{"id": "primary", "summary": "My Calendar"}]
    events = {
        "primary": [
            {"id": "evt1", "summary": "Meeting", "start": {"dateTime": "2026-03-23T10:00:00Z"}},
            {"id": "evt2", "summary": "Lunch", "start": {"dateTime": "2026-03-23T12:00:00Z"}},
        ],
    }

    mock_api = _mock_calendar_api(calendars, events)
    state = ServiceState.load(tmp_path / "state", "calendar")
    backup_dir = tmp_path / "calendar"

    with patch("google_backup.services.calendar.build", return_value=mock_api):
        svc = CalendarService()
        result = svc.sync(MagicMock(), state, backup_dir)

    assert result.items_synced == 2
    assert (backup_dir / "primary" / "evt1.json").exists()
    data = json.loads((backup_dir / "primary" / "evt1.json").read_text())
    assert data["summary"] == "Meeting"

    # Sync token should be stored in the state object
    assert "primary" in state.data.get("sync_tokens", {})


def test_calendar_incremental_sync(tmp_path):
    """When sync token exists, pass it to the API."""
    state = ServiceState.load(tmp_path / "state", "calendar")
    state.data["sync_tokens"] = {"primary": "old_token"}
    state.data["calendars"] = ["primary"]
    state.save()

    calendars = [{"id": "primary", "summary": "My Calendar"}]
    events = {
        "primary": [{"id": "evt3", "summary": "New Event", "start": {"dateTime": "2026-03-24T09:00:00Z"}}],
    }
    mock_api = _mock_calendar_api(calendars, events, next_sync_token="new_token")

    with patch("google_backup.services.calendar.build", return_value=mock_api):
        svc = CalendarService()
        result = svc.sync(MagicMock(), state, tmp_path / "calendar")

    # Verify syncToken was passed
    call_kwargs = mock_api.events.return_value.list.call_args
    assert call_kwargs.kwargs.get("syncToken") == "old_token" or \
           (call_kwargs[1].get("syncToken") == "old_token")


def test_calendar_cancelled_event(tmp_path):
    """Cancelled events should be written with status: cancelled."""
    calendars = [{"id": "primary", "summary": "My Calendar"}]
    events = {
        "primary": [{"id": "evt_del", "status": "cancelled"}],
    }
    mock_api = _mock_calendar_api(calendars, events)
    state = ServiceState.load(tmp_path / "state", "calendar")

    with patch("google_backup.services.calendar.build", return_value=mock_api):
        svc = CalendarService()
        result = svc.sync(MagicMock(), state, tmp_path / "calendar")

    data = json.loads((tmp_path / "calendar" / "primary" / "evt_del.json").read_text())
    assert data["status"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_calendar.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement calendar.py**

```python
# scripts/backup/google-backup/google_backup/services/calendar.py
"""Google Calendar backup service — syncToken-based incremental."""

import json
import logging
import time
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from google_backup.services import register
from google_backup.services.base import BaseService, SyncResult
from google_backup.state import ServiceState

log = logging.getLogger(__name__)


@register
class CalendarService(BaseService):
    name = "calendar"
    scopes = ("https://www.googleapis.com/auth/calendar.readonly",)

    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        start = time.time()
        service = build("calendar", "v3", credentials=creds)
        sync_tokens = state.data.get("sync_tokens", {})
        items_synced = 0
        items_failed = 0
        items_deleted = 0
        failed_ids: list[str] = []

        # Get all calendars
        cal_list = service.calendarList().list().execute()
        calendars = cal_list.get("items", [])

        new_sync_tokens = {}

        for cal in calendars:
            cal_id = cal["id"]
            cal_dir = backup_dir / cal_id
            cal_dir.mkdir(parents=True, exist_ok=True)

            try:
                existing_token = sync_tokens.get(cal_id)
                list_kwargs: dict = {"calendarId": cal_id}

                if existing_token:
                    # Incremental: use syncToken (singleEvents NOT allowed with syncToken)
                    list_kwargs["syncToken"] = existing_token
                else:
                    # Full sync: singleEvents expands recurring events
                    list_kwargs["singleEvents"] = True
                    log.info("Full sync for calendar: %s", cal.get("summary", cal_id))

                # Paginate through events
                events_resource = service.events()
                request = events_resource.list(**list_kwargs)
                while request:
                    response = request.execute()
                    new_sync_tokens[cal_id] = response.get("nextSyncToken", "")

                    for event in response.get("items", []):
                        event_id = event["id"]
                        try:
                            (cal_dir / f"{event_id}.json").write_text(
                                json.dumps(event, indent=2, ensure_ascii=False) + "\n"
                            )
                            if event.get("status") == "cancelled":
                                items_deleted += 1
                            else:
                                items_synced += 1
                        except Exception as e:
                            log.error("Failed to write event %s: %s", event_id, e)
                            items_failed += 1
                            failed_ids.append(event_id)

                    request = events_resource.list_next(request, response)

            except Exception as e:
                log.error("Failed to sync calendar %s: %s", cal_id, e)
                items_failed += 1
                failed_ids.append(f"calendar:{cal_id}")

        # Persist sync tokens (saved by cmd_sync after this returns)
        state.data["sync_tokens"] = new_sync_tokens
        state.data["calendars"] = [c["id"] for c in calendars]

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=items_deleted,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_calendar.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/services/calendar.py \
       scripts/backup/google-backup/tests/test_calendar.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add Calendar service with syncToken incremental sync"
```

---

### Task 10: Contacts service (syncToken incremental)

**Files:**
- Create: `scripts/backup/google-backup/google_backup/services/contacts.py`
- Create: `scripts/backup/google-backup/tests/test_contacts.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_contacts.py
"""Tests for Google Contacts backup service."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from google_backup.services.contacts import ContactsService
from google_backup.state import ServiceState


def _mock_people_api(connections, next_sync_token="sync_abc"):
    """Build a mock People API service."""
    service = MagicMock()

    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "connections": connections,
        "nextSyncToken": next_sync_token,
        "totalPeople": len(connections),
    }

    service.people.return_value.connections.return_value.list.return_value = mock_list
    # Pagination termination on the resource, not the request
    service.people.return_value.connections.return_value.list_next.return_value = None
    return service


def test_contacts_full_sync(tmp_path):
    connections = [
        {
            "resourceName": "people/c123",
            "names": [{"displayName": "Alice Smith"}],
            "emailAddresses": [{"value": "alice@example.com"}],
        },
        {
            "resourceName": "people/c456",
            "names": [{"displayName": "Bob Jones"}],
        },
    ]

    mock_api = _mock_people_api(connections)
    state = ServiceState.load(tmp_path / "state", "contacts")

    with patch("google_backup.services.contacts.build", return_value=mock_api):
        svc = ContactsService()
        result = svc.sync(MagicMock(), state, tmp_path / "contacts")

    assert result.items_synced == 2
    assert (tmp_path / "contacts" / "c123.vcf").exists()
    assert (tmp_path / "contacts" / "c123.json").exists()

    vcf_content = (tmp_path / "contacts" / "c123.vcf").read_text()
    assert "Alice Smith" in vcf_content
    assert "alice@example.com" in vcf_content


def test_contacts_deleted_contact(tmp_path):
    """Deleted contacts should have metadata marked but VCF kept."""
    # Pre-existing contact
    backup_dir = tmp_path / "contacts"
    backup_dir.mkdir(parents=True)
    (backup_dir / "c789.vcf").write_text("BEGIN:VCARD\nFN:Old Contact\nEND:VCARD")
    (backup_dir / "c789.json").write_text('{"resourceName": "people/c789"}')

    connections = [
        {
            "resourceName": "people/c789",
            "metadata": {"deleted": True},
        },
    ]
    mock_api = _mock_people_api(connections)
    state = ServiceState.load(tmp_path / "state", "contacts")

    with patch("google_backup.services.contacts.build", return_value=mock_api):
        svc = ContactsService()
        result = svc.sync(MagicMock(), state, backup_dir)

    # VCF should still exist
    assert (backup_dir / "c789.vcf").exists()
    # Metadata should show deleted
    data = json.loads((backup_dir / "c789.json").read_text())
    assert data.get("deleted") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_contacts.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement contacts.py**

```python
# scripts/backup/google-backup/google_backup/services/contacts.py
"""Google Contacts backup service — syncToken-based incremental."""

import json
import logging
import time
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from google_backup.services import register
from google_backup.services.base import BaseService, SyncResult
from google_backup.state import ServiceState

log = logging.getLogger(__name__)


def _to_vcf(person: dict) -> str:
    """Convert a People API person resource to a minimal vCard string."""
    lines = ["BEGIN:VCARD", "VERSION:3.0"]

    names = person.get("names", [])
    if names:
        display_name = names[0].get("displayName", "")
        lines.append(f"FN:{display_name}")
        family = names[0].get("familyName", "")
        given = names[0].get("givenName", "")
        if family or given:
            lines.append(f"N:{family};{given};;;")

    for email in person.get("emailAddresses", []):
        lines.append(f"EMAIL:{email['value']}")

    for phone in person.get("phoneNumbers", []):
        lines.append(f"TEL:{phone['value']}")

    for org in person.get("organizations", []):
        name = org.get("name", "")
        title = org.get("title", "")
        if name:
            lines.append(f"ORG:{name}")
        if title:
            lines.append(f"TITLE:{title}")

    for addr in person.get("addresses", []):
        formatted = addr.get("formattedValue", "").replace("\n", "\\n")
        if formatted:
            lines.append(f"ADR:;;{formatted};;;;")

    lines.append("END:VCARD")
    return "\n".join(lines) + "\n"


@register
class ContactsService(BaseService):
    name = "contacts"
    scopes = ("https://www.googleapis.com/auth/contacts.readonly",)

    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        start = time.time()
        service = build("people", "v1", credentials=creds)
        backup_dir.mkdir(parents=True, exist_ok=True)

        items_synced = 0
        items_failed = 0
        items_deleted = 0
        failed_ids: list[str] = []

        # Build list kwargs
        list_kwargs: dict = {
            "resourceName": "people/me",
            "personFields": "names,emailAddresses,phoneNumbers,organizations,addresses",
            "pageSize": 100,
            "requestSyncToken": True,
        }
        existing_token = state.data.get("sync_token")
        if existing_token:
            list_kwargs["syncToken"] = existing_token
        else:
            log.info("Full sync for contacts")

        # Paginate through all connections
        connections_resource = service.people().connections()
        request = connections_resource.list(**list_kwargs)
        next_sync_token = None

        while request:
            response = request.execute()
            next_sync_token = response.get("nextSyncToken", next_sync_token)
            connections = response.get("connections", [])

            for person in connections:
                resource_name = person.get("resourceName", "")
                person_id = resource_name.replace("people/", "")

                if not person_id:
                    continue

                # Check if deleted
                is_deleted = person.get("metadata", {}).get("deleted", False)

                try:
                    if is_deleted:
                        # Mark metadata as deleted, keep VCF
                        meta_path = backup_dir / f"{person_id}.json"
                        person["deleted"] = True
                        meta_path.write_text(
                            json.dumps(person, indent=2, ensure_ascii=False) + "\n"
                        )
                        items_deleted += 1
                        log.info("Contact deleted: %s", person_id)
                    else:
                        # Write VCF and metadata
                        (backup_dir / f"{person_id}.vcf").write_text(_to_vcf(person))
                        (backup_dir / f"{person_id}.json").write_text(
                            json.dumps(person, indent=2, ensure_ascii=False) + "\n"
                        )
                        items_synced += 1
                except Exception as e:
                    log.error("Failed to write contact %s: %s", person_id, e)
                    items_failed += 1
                    failed_ids.append(person_id)

            request = connections_resource.list_next(request, response)

        # Persist sync token (saved by cmd_sync after this returns)
        if next_sync_token:
            state.data["sync_token"] = next_sync_token

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=items_deleted,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_contacts.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/services/contacts.py \
       scripts/backup/google-backup/tests/test_contacts.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add Contacts service with vCard export and incremental sync"
```

---

### Task 11: Gmail service (historyId incremental with checkpointing)

**Files:**
- Create: `scripts/backup/google-backup/google_backup/services/gmail.py`
- Create: `scripts/backup/google-backup/tests/test_gmail.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_gmail.py
"""Tests for Gmail backup service."""
import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from google_backup.services.gmail import GmailService, CHECKPOINT_INTERVAL
from google_backup.state import ServiceState


def _mock_gmail_api(messages, message_details, history=None, profile_history_id="99999"):
    """Build a mock Gmail API service."""
    service = MagicMock()

    # users().getProfile()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "historyId": profile_history_id,
    }

    # users().messages().list() — paginated
    list_mock = MagicMock()
    list_mock.execute.return_value = {
        "messages": [{"id": m} for m in messages],
        "resultSizeEstimate": len(messages),
    }
    service.users.return_value.messages.return_value.list.return_value = list_mock
    service.users.return_value.messages.return_value.list_next.return_value = None

    # users().messages().get()
    def _get_message(userId, id, format="raw"):
        mock = MagicMock()
        detail = message_details.get(id, {
            "id": id,
            "raw": base64.urlsafe_b64encode(b"From: test@test.com\nSubject: Test\n\nBody").decode(),
            "labelIds": ["INBOX"],
            "threadId": "thread1",
            "internalDate": "1711152000000",
        })
        mock.execute.return_value = detail
        return mock

    service.users.return_value.messages.return_value.get.side_effect = _get_message

    # users().history().list()
    if history is not None:
        hist_mock = MagicMock()
        hist_mock.execute.return_value = history
        service.users.return_value.history.return_value.list.return_value = hist_mock
        service.users.return_value.history.return_value.list_next.return_value = None

    return service


def test_gmail_full_sync(tmp_path):
    raw_email = base64.urlsafe_b64encode(
        b"From: alice@example.com\nSubject: Hello\n\nHi there"
    ).decode()

    messages = ["msg1", "msg2"]
    details = {
        "msg1": {
            "id": "msg1", "raw": raw_email,
            "labelIds": ["INBOX"], "threadId": "t1", "internalDate": "1711152000000",
        },
        "msg2": {
            "id": "msg2", "raw": raw_email,
            "labelIds": ["SENT"], "threadId": "t2", "internalDate": "1711152000000",
        },
    }

    mock_api = _mock_gmail_api(messages, details)
    state = ServiceState.load(tmp_path / "state", "gmail")

    with patch("google_backup.services.gmail.build", return_value=mock_api):
        svc = GmailService()
        result = svc.sync(MagicMock(), state, tmp_path / "gmail")

    assert result.items_synced == 2
    assert (tmp_path / "gmail" / "msg1" / "message.eml").exists()
    assert (tmp_path / "gmail" / "msg1" / "metadata.json").exists()
    assert (tmp_path / "gmail" / "msg2" / "message.eml").exists()

    meta = json.loads((tmp_path / "gmail" / "msg1" / "metadata.json").read_text())
    assert meta["labelIds"] == ["INBOX"]


def test_gmail_incremental_sync(tmp_path):
    """When historyId exists, use history API for incremental."""
    state = ServiceState.load(tmp_path / "state", "gmail")
    state.data["history_id"] = "10000"
    state.save()

    raw_email = base64.urlsafe_b64encode(b"From: new@example.com\nSubject: New\n\nNew msg").decode()

    history = {
        "history": [
            {"messagesAdded": [{"message": {"id": "msg_new"}}]},
        ],
        "historyId": "10001",
    }

    details = {
        "msg_new": {
            "id": "msg_new", "raw": raw_email,
            "labelIds": ["INBOX"], "threadId": "t3", "internalDate": "1711239000000",
        },
    }

    mock_api = _mock_gmail_api([], details, history=history)

    with patch("google_backup.services.gmail.build", return_value=mock_api):
        svc = GmailService()
        result = svc.sync(MagicMock(), state, tmp_path / "gmail")

    assert result.items_synced == 1
    assert (tmp_path / "gmail" / "msg_new" / "message.eml").exists()


def test_gmail_deletion_marks_metadata(tmp_path):
    """Deleted messages should have metadata marked, EML kept."""
    # Pre-existing message
    msg_dir = tmp_path / "gmail" / "msg_del"
    msg_dir.mkdir(parents=True)
    (msg_dir / "message.eml").write_text("From: old@test.com\nSubject: Old")
    (msg_dir / "metadata.json").write_text('{"id": "msg_del", "labelIds": ["INBOX"]}')

    state = ServiceState.load(tmp_path / "state", "gmail")
    state.data["history_id"] = "10000"
    state.save()

    history = {
        "history": [
            {"messagesDeleted": [{"message": {"id": "msg_del"}}]},
        ],
        "historyId": "10001",
    }

    mock_api = _mock_gmail_api([], {}, history=history)

    with patch("google_backup.services.gmail.build", return_value=mock_api):
        svc = GmailService()
        result = svc.sync(MagicMock(), state, tmp_path / "gmail")

    # EML should still exist
    assert (msg_dir / "message.eml").exists()
    # Metadata should show deleted
    meta = json.loads((msg_dir / "metadata.json").read_text())
    assert meta.get("deleted") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_gmail.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement gmail.py**

```python
# scripts/backup/google-backup/google_backup/services/gmail.py
"""Gmail backup service — historyId-based incremental with checkpointing."""

import base64
import json
import logging
import time
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from google_backup.services import register
from google_backup.services.base import BaseService, SyncResult
from google_backup.state import ServiceState

log = logging.getLogger(__name__)

CHECKPOINT_INTERVAL = 500


@register
class GmailService(BaseService):
    name = "gmail"
    scopes = ("https://www.googleapis.com/auth/gmail.readonly",)

    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        start = time.time()
        service = build("gmail", "v1", credentials=creds)
        backup_dir.mkdir(parents=True, exist_ok=True)

        existing_history_id = state.data.get("history_id")

        if existing_history_id:
            return self._incremental_sync(service, state, backup_dir, existing_history_id, start)
        else:
            return self._full_sync(service, state, backup_dir, start)

    def _full_sync(self, service, state: ServiceState, backup_dir: Path, start: float) -> SyncResult:
        """Download all messages. Checkpoint every CHECKPOINT_INTERVAL messages."""
        log.info("Starting full Gmail sync (this may take a while for large accounts)")
        items_synced = 0
        items_failed = 0
        failed_ids: list[str] = []

        # Resume from partial cursor if interrupted
        page_token = state.get_partial_cursor()
        if page_token:
            log.info("Resuming from partial cursor")

        # Get current historyId
        profile = service.users().getProfile(userId="me").execute()
        history_id = profile["historyId"]

        while True:
            list_kwargs = {"userId": "me", "maxResults": 100}
            if page_token:
                list_kwargs["pageToken"] = page_token

            response = service.users().messages().list(**list_kwargs).execute()
            messages = response.get("messages", [])

            for msg_stub in messages:
                msg_id = msg_stub["id"]
                try:
                    self._download_message(service, msg_id, backup_dir)
                    items_synced += 1
                except Exception as e:
                    log.error("Failed to download message %s: %s", msg_id, e)
                    items_failed += 1
                    failed_ids.append(msg_id)

                # Checkpoint
                if items_synced % CHECKPOINT_INTERVAL == 0 and items_synced > 0:
                    log.info("Checkpoint: %d messages synced", items_synced)
                    state.set_partial_cursor(response.get("nextPageToken", ""))

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        # Full sync complete — save historyId
        state.data["history_id"] = history_id

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=0,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )

    def _incremental_sync(
        self, service, state: ServiceState, backup_dir: Path,
        history_id: str, start: float,
    ) -> SyncResult:
        """Use History API to sync only changes since last run."""
        log.info("Incremental sync from historyId %s", history_id)
        items_synced = 0
        items_failed = 0
        items_deleted = 0
        failed_ids: list[str] = []
        new_history_id = history_id

        request = service.users().history().list(
            userId="me", startHistoryId=history_id,
            historyTypes=["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"],
        )

        while request:
            response = request.execute()
            new_history_id = response.get("historyId", new_history_id)

            for record in response.get("history", []):
                # New messages
                for added in record.get("messagesAdded", []):
                    msg_id = added["message"]["id"]
                    try:
                        self._download_message(service, msg_id, backup_dir)
                        items_synced += 1
                    except Exception as e:
                        log.error("Failed to download message %s: %s", msg_id, e)
                        items_failed += 1
                        failed_ids.append(msg_id)

                # Deleted messages — mark metadata, keep EML
                for deleted in record.get("messagesDeleted", []):
                    msg_id = deleted["message"]["id"]
                    meta_path = backup_dir / msg_id / "metadata.json"
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text())
                            meta["deleted"] = True
                            meta_path.write_text(
                                json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
                            )
                            items_deleted += 1
                            log.info("Message deleted: %s", msg_id)
                        except Exception as e:
                            log.error("Failed to mark deletion for %s: %s", msg_id, e)

                # Label changes — re-download metadata
                for label_change in record.get("labelsAdded", []) + record.get("labelsRemoved", []):
                    msg_id = label_change["message"]["id"]
                    try:
                        self._download_message(service, msg_id, backup_dir)
                        items_synced += 1
                    except Exception as e:
                        log.error("Failed to update labels for %s: %s", msg_id, e)

            request = service.users().history().list_next(request, response)

        state.data["history_id"] = new_history_id

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=items_deleted,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )

    def _download_message(self, service, msg_id: str, backup_dir: Path) -> None:
        """Download a single message as EML + metadata JSON."""
        msg_dir = backup_dir / msg_id
        msg_dir.mkdir(parents=True, exist_ok=True)

        msg = service.users().messages().get(userId="me", id=msg_id, format="raw").execute()

        # Write raw EML
        raw_bytes = base64.urlsafe_b64decode(msg["raw"])
        (msg_dir / "message.eml").write_bytes(raw_bytes)

        # Write metadata (everything except the raw body)
        metadata = {k: v for k, v in msg.items() if k != "raw"}
        (msg_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_gmail.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/services/gmail.py \
       scripts/backup/google-backup/tests/test_gmail.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add Gmail service with historyId incremental sync and checkpointing"
```

---

### Task 12: Drive service (changes token, file download, symlinks)

**Files:**
- Create: `scripts/backup/google-backup/google_backup/services/drive.py`
- Create: `scripts/backup/google-backup/tests/test_drive.py`

- [ ] **Step 1: Write the tests**

```python
# scripts/backup/google-backup/tests/test_drive.py
"""Tests for Google Drive backup service."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from google_backup.services.drive import DriveService
from google_backup.state import ServiceState
from google_backup.state import ServiceState


def _mock_drive_api(files, start_page_token="token1", new_page_token="token2", changes=None):
    """Build a mock Google Drive API service."""
    service = MagicMock()

    # changes().getStartPageToken()
    service.changes.return_value.getStartPageToken.return_value.execute.return_value = {
        "startPageToken": start_page_token,
    }

    # files().list() for full sync
    list_mock = MagicMock()
    list_mock.execute.return_value = {
        "files": files,
    }
    service.files.return_value.list.return_value = list_mock
    service.files.return_value.list_next.return_value = None

    # files().get_media() for downloading
    def _get_media(fileId, **kwargs):
        mock = MagicMock()
        mock.execute.return_value = b"file content here"
        return mock
    service.files.return_value.get_media.side_effect = _get_media

    # files().export_media() for Google Docs
    def _export_media(fileId, mimeType, **kwargs):
        mock = MagicMock()
        mock.execute.return_value = b"%PDF-1.4 fake pdf content"
        return mock
    service.files.return_value.export_media.side_effect = _export_media

    # files().get() for metadata
    def _get_file(fileId, fields=None):
        mock = MagicMock()
        for f in files:
            if f["id"] == fileId:
                mock.execute.return_value = f
                return mock
        mock.execute.return_value = {"id": fileId, "name": "unknown"}
        return mock
    service.files.return_value.get.side_effect = _get_file

    # changes().list() for incremental
    if changes is not None:
        ch_mock = MagicMock()
        ch_mock.execute.return_value = {
            "changes": changes,
            "newStartPageToken": new_page_token,
        }
        service.changes.return_value.list.return_value = ch_mock
        service.changes.return_value.list_next.return_value = None

    return service


def test_drive_full_sync(tmp_path):
    files = [
        {
            "id": "file1",
            "name": "document.txt",
            "mimeType": "text/plain",
            "parents": ["root"],
        },
        {
            "id": "file2",
            "name": "My Doc",
            "mimeType": "application/vnd.google-apps.document",
            "parents": ["root"],
        },
    ]

    mock_api = _mock_drive_api(files)

    state = ServiceState.load(tmp_path / "state", "drive")

    with patch("google_backup.services.drive.build", return_value=mock_api):
        with patch("google_backup.services.drive.MediaIoBaseDownload") as mock_dl:
            # Make download return immediately
            mock_dl_instance = MagicMock()
            mock_dl_instance.next_chunk.return_value = (MagicMock(progress=lambda: 1.0), True)
            mock_dl.return_value = mock_dl_instance

            svc = DriveService()
            result = svc.sync(MagicMock(), state, tmp_path / "drive")

    assert result.items_synced == 2
    assert (tmp_path / "drive" / "by_id" / "file1" / "metadata.json").exists()
    assert (tmp_path / "drive" / "by_id" / "file2" / "metadata.json").exists()

    meta = json.loads((tmp_path / "drive" / "by_id" / "file1" / "metadata.json").read_text())
    assert meta["name"] == "document.txt"


def test_drive_disk_limit_skips_sync(tmp_path):
    """When backup dir exceeds GOOGLE_BACKUP_MAX_DISK_GB, drive sync is skipped."""
    backup_dir = tmp_path / "drive"
    backup_dir.mkdir(parents=True)
    # Create a file to make the parent dir non-empty
    (backup_dir / "dummy").write_text("x" * 1024)

    state = ServiceState.load(tmp_path / "state", "drive")

    with patch.dict(os.environ, {"GOOGLE_BACKUP_MAX_DISK_GB": "0"}):
        svc = DriveService()
        result = svc.sync(MagicMock(), state, backup_dir)

    assert result.items_synced == 0


def test_drive_trashed_file_keeps_local_copy(tmp_path):
    """Trashed files should update metadata but keep the local file."""
    # Pre-existing file
    by_id = tmp_path / "drive" / "by_id" / "file_trash"
    by_id.mkdir(parents=True)
    (by_id / "content.txt").write_text("important data")
    (by_id / "metadata.json").write_text('{"id": "file_trash", "name": "old.txt"}')

    state = ServiceState.load(tmp_path / "state", "drive")
    state.data["page_token"] = "old_token"
    state.save()

    changes = [
        {"fileId": "file_trash", "removed": False, "file": {
            "id": "file_trash", "name": "old.txt", "trashed": True,
            "mimeType": "text/plain", "parents": ["root"],
        }},
    ]

    mock_api = _mock_drive_api([], changes=changes)

    with patch("google_backup.services.drive.build", return_value=mock_api):
        svc = DriveService()
        result = svc.sync(MagicMock(), state, tmp_path / "drive")

    # Local file should still exist
    assert (by_id / "content.txt").exists()
    # Metadata should show trashed
    meta = json.loads((by_id / "metadata.json").read_text())
    assert meta.get("trashed") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_drive.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement drive.py**

```python
# scripts/backup/google-backup/google_backup/services/drive.py
"""Google Drive backup service — changes token with file download and symlink tree."""

import io
import json
import logging
import os
import shutil
import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials

from google_backup.services import register
from google_backup.services.base import BaseService, SyncResult
from google_backup.state import ServiceState

log = logging.getLogger(__name__)

# Google Workspace MIME types that need export
EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}

# Google Workspace types that can't be downloaded (no export possible)
SKIP_MIME_TYPES = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.shortcut",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.site",
}

CHECKPOINT_INTERVAL = 500


def _check_disk_limit(backup_root: Path) -> bool:
    """Check if backup root's parent dir exceeds GOOGLE_BACKUP_MAX_DISK_GB. Returns True if OK."""
    limit_gb = os.environ.get("GOOGLE_BACKUP_MAX_DISK_GB")
    if not limit_gb:
        return True
    try:
        limit_bytes = float(limit_gb) * 1024 * 1024 * 1024
    except ValueError:
        return True

    if not backup_root.parent.exists():
        return True

    # Sum up the total backup directory size
    total = sum(f.stat().st_size for f in backup_root.parent.rglob("*") if f.is_file())
    if total > limit_bytes:
        log.warning(
            "Backup directory (%.1f GB) exceeds limit (%.1f GB). Skipping Drive sync.",
            total / (1024**3), float(limit_gb),
        )
        return False
    return True


@register
class DriveService(BaseService):
    name = "drive"
    scopes = ("https://www.googleapis.com/auth/drive.readonly",)

    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        start = time.time()

        # Disk limit check
        if not _check_disk_limit(backup_dir):
            return SyncResult(
                service=self.name, items_synced=0, items_failed=0,
                items_deleted=0, elapsed_seconds=time.time() - start,
            )

        service = build("drive", "v3", credentials=creds)
        by_id_dir = backup_dir / "by_id"
        by_id_dir.mkdir(parents=True, exist_ok=True)

        existing_token = state.data.get("page_token")

        if existing_token:
            result = self._incremental_sync(service, state, backup_dir, by_id_dir, existing_token, start)
        else:
            result = self._full_sync(service, state, backup_dir, by_id_dir, start)

        # Rebuild symlink tree after sync
        self._rebuild_tree(by_id_dir, backup_dir / "tree")

        return result

    def _full_sync(
        self, service, state: ServiceState, backup_dir: Path,
        by_id_dir: Path, start: float,
    ) -> SyncResult:
        log.info("Starting full Drive sync")
        items_synced = 0
        items_failed = 0
        failed_ids: list[str] = []

        # Get starting page token for future incremental syncs
        token_response = service.changes().getStartPageToken().execute()
        start_page_token = token_response["startPageToken"]

        page_token = state.get_partial_cursor()
        if page_token:
            log.info("Resuming from partial cursor")

        while True:
            list_kwargs = {
                "q": "trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, parents, modifiedTime, size)",
                "pageSize": 100,
            }
            if page_token:
                list_kwargs["pageToken"] = page_token

            response = service.files().list(**list_kwargs).execute()
            files = response.get("files", [])

            for file_meta in files:
                file_id = file_meta["id"]
                mime_type = file_meta.get("mimeType", "")

                if mime_type in SKIP_MIME_TYPES:
                    continue

                try:
                    self._download_file(service, file_meta, by_id_dir)
                    items_synced += 1
                except Exception as e:
                    log.error("Failed to download file %s (%s): %s", file_id, file_meta.get("name"), e)
                    items_failed += 1
                    failed_ids.append(file_id)

                if items_synced % CHECKPOINT_INTERVAL == 0 and items_synced > 0:
                    log.info("Checkpoint: %d files synced", items_synced)
                    state.set_partial_cursor(response.get("nextPageToken", ""))

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        state.data["page_token"] = start_page_token

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=0,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )

    def _incremental_sync(
        self, service, state: ServiceState, backup_dir: Path,
        by_id_dir: Path, page_token: str, start: float,
    ) -> SyncResult:
        log.info("Incremental Drive sync from token %s", page_token[:20])
        items_synced = 0
        items_failed = 0
        items_deleted = 0
        failed_ids: list[str] = []
        new_token = page_token

        request = service.changes().list(
            pageToken=page_token,
            fields="nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, parents, modifiedTime, size, trashed))",
            pageSize=100,
        )

        while request:
            response = request.execute()
            new_token = response.get("newStartPageToken", new_token)

            for change in response.get("changes", []):
                file_id = change["fileId"]
                file_meta = change.get("file", {})
                is_removed = change.get("removed", False)
                is_trashed = file_meta.get("trashed", False)

                if is_removed or is_trashed:
                    # Update metadata to reflect trashed/removed state
                    meta_path = by_id_dir / file_id / "metadata.json"
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text())
                            meta["trashed"] = True
                            meta_path.write_text(
                                json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
                            )
                            items_deleted += 1
                        except Exception as e:
                            log.error("Failed to mark trashed %s: %s", file_id, e)
                    continue

                mime_type = file_meta.get("mimeType", "")
                if mime_type in SKIP_MIME_TYPES:
                    continue

                try:
                    self._download_file(service, file_meta, by_id_dir)
                    items_synced += 1
                except Exception as e:
                    log.error("Failed to download changed file %s: %s", file_id, e)
                    items_failed += 1
                    failed_ids.append(file_id)

            request = service.changes().list_next(request, response)

        state.data["page_token"] = new_token

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=items_deleted,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )

    def _download_file(self, service, file_meta: dict, by_id_dir: Path) -> None:
        """Download a single file to by_id/<file_id>/."""
        file_id = file_meta["id"]
        file_dir = by_id_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)

        mime_type = file_meta.get("mimeType", "")

        # Write metadata
        (file_dir / "metadata.json").write_text(
            json.dumps(file_meta, indent=2, ensure_ascii=False) + "\n"
        )

        # Download content
        if mime_type in EXPORT_MIME_TYPES:
            export_mime, ext = EXPORT_MIME_TYPES[mime_type]
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
            filename = f"content{ext}"
        elif mime_type in SKIP_MIME_TYPES:
            return
        else:
            request = service.files().get_media(fileId=file_id)
            name = file_meta.get("name", "content")
            filename = name

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        (file_dir / filename).write_bytes(fh.getvalue())

    def _rebuild_tree(self, by_id_dir: Path, tree_dir: Path) -> None:
        """Rebuild the symlink tree from by_id metadata."""
        if tree_dir.exists():
            shutil.rmtree(tree_dir)
        tree_dir.mkdir(parents=True, exist_ok=True)

        # Build folder name map (id -> name) and parent map
        folder_names: dict[str, str] = {"root": ""}
        file_entries: list[tuple[str, str, list[str]]] = []  # (file_id, name, parents)

        for file_dir in by_id_dir.iterdir():
            if not file_dir.is_dir():
                continue
            meta_path = file_dir / "metadata.json"
            if not meta_path.exists():
                continue
            meta = json.loads(meta_path.read_text())
            if meta.get("trashed"):
                continue
            file_id = meta["id"]
            name = meta.get("name", file_id)
            parents = meta.get("parents", [])
            mime_type = meta.get("mimeType", "")

            if mime_type == "application/vnd.google-apps.folder":
                folder_names[file_id] = name
            else:
                file_entries.append((file_id, name, parents))

        # Resolve folder paths
        def resolve_path(folder_id: str, seen: set | None = None) -> Path:
            if seen is None:
                seen = set()
            if folder_id in seen or folder_id == "root" or folder_id not in folder_names:
                return tree_dir
            seen.add(folder_id)
            # Find this folder's parent
            meta_path = by_id_dir / folder_id / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                parent_ids = meta.get("parents", [])
                if parent_ids:
                    parent_path = resolve_path(parent_ids[0], seen)
                    return parent_path / folder_names[folder_id]
            return tree_dir / folder_names.get(folder_id, folder_id)

        # Create symlinks
        for file_id, name, parents in file_entries:
            for parent_id in parents:
                parent_path = resolve_path(parent_id)
                parent_path.mkdir(parents=True, exist_ok=True)
                link_path = parent_path / name
                target = by_id_dir / file_id

                # Avoid duplicate names
                if link_path.exists() or link_path.is_symlink():
                    link_path = parent_path / f"{name}_{file_id[:8]}"

                try:
                    link_path.symlink_to(target)
                except OSError as e:
                    log.warning("Failed to create symlink %s -> %s: %s", link_path, target, e)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/backup/google-backup
python -m pytest tests/test_drive.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/google-backup/google_backup/services/drive.py \
       scripts/backup/google-backup/tests/test_drive.py
git commit --author="Claude <noreply@anthropic.com>" \
  -m "feat(backup): add Drive service with incremental sync and symlink tree"
```

---

### Task 13: Run full test suite and final commit

**Files:**
- No new files

- [ ] **Step 1: Install dependencies in venv**

```bash
cd scripts/backup/google-backup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

- [ ] **Step 2: Run entire test suite**

```bash
cd scripts/backup/google-backup
python -m pytest tests/ -v
```

Expected: All tests pass (approximately 20 tests across 7 test files).

- [ ] **Step 3: Run shellcheck on run.sh**

```bash
shellcheck scripts/backup/google-backup/run.sh
```

Expected: No errors.

- [ ] **Step 4: Verify CLI help works**

```bash
cd scripts/backup/google-backup
source .venv/bin/activate
python -m google_backup --help
```

Expected: Shows usage with --all, --gmail, --calendar, etc.

- [ ] **Step 5: Verify --status works without credentials**

```bash
cd scripts/backup/google-backup
source .venv/bin/activate
GOOGLE_BACKUP_CLIENT_SECRET=/tmp/fake GOOGLE_BACKUP_DIR=/tmp/test-backup \
  python -m google_backup --status
```

Expected: Shows "Never synced" for all 6 services.

- [ ] **Step 6: Add .venv to .gitignore**

Add to the project-level `.gitignore`:

```
scripts/backup/google-backup/.venv/
```

- [ ] **Step 7: Final commit**

```bash
git add .gitignore
git commit --author="Claude <noreply@anthropic.com>" \
  -m "chore: add google-backup venv to gitignore"
```
