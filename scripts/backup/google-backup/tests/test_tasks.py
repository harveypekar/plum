"""Tests for Google Tasks backup service."""
import json
from unittest.mock import MagicMock, patch

from google_backup.services.tasks import TasksService
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
