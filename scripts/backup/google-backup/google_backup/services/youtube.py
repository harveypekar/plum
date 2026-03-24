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
