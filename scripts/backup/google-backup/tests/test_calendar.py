"""Tests for Google Calendar backup service."""
import json
from unittest.mock import MagicMock, patch

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
        svc.sync(MagicMock(), state, tmp_path / "calendar")

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
        svc.sync(MagicMock(), state, tmp_path / "calendar")

    data = json.loads((tmp_path / "calendar" / "primary" / "evt_del.json").read_text())
    assert data["status"] == "cancelled"
