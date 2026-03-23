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
