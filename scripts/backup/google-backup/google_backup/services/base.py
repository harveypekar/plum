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
