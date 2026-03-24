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
