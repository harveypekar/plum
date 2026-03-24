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
