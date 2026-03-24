"""Tests for Google Drive backup service."""
import json
import os
from unittest.mock import MagicMock, patch

from google_backup.services.drive import DriveService
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
        svc.sync(MagicMock(), state, tmp_path / "drive")

    # Local file should still exist
    assert (by_id / "content.txt").exists()
    # Metadata should show trashed
    meta = json.loads((by_id / "metadata.json").read_text())
    assert meta.get("trashed") is True
