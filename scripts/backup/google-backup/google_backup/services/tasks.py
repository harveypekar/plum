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
