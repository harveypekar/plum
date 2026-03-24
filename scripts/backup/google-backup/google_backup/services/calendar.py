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
