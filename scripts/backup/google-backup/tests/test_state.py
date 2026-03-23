"""Tests for sync state management."""
import json

from google_backup.state import ServiceState


def test_load_returns_empty_for_missing_file(tmp_path):
    state = ServiceState.load(tmp_path / "state", "gmail")
    assert state.data == {}
    assert state.service == "gmail"


def test_save_and_load_roundtrip(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")
    state.data["history_id"] = "12345"
    state.save()

    reloaded = ServiceState.load(state_dir, "gmail")
    assert reloaded.data["history_id"] == "12345"


def test_save_writes_last_run(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")
    state.save()

    raw = json.loads((state_dir / "gmail.json").read_text())
    assert "last_run" in raw


def test_partial_cursor_lifecycle(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")

    # Set partial cursor during long sync
    state.set_partial_cursor("page_token_abc")
    assert state.get_partial_cursor() == "page_token_abc"

    # Clear on successful completion
    state.clear_partial_cursor()
    assert state.get_partial_cursor() is None

    # Partial cursor persists across loads (for crash recovery)
    state2 = ServiceState.load(state_dir, "gmail")
    state2.set_partial_cursor("page_token_xyz")
    # Not calling save() here — set_partial_cursor writes immediately
    state3 = ServiceState.load(state_dir, "gmail")
    assert state3.get_partial_cursor() == "page_token_xyz"


def test_status_report(tmp_path):
    state_dir = tmp_path / "state"
    state = ServiceState.load(state_dir, "gmail")
    state.data["history_id"] = "99999"
    state.data["items_backed_up"] = 5000
    state.save()

    reloaded = ServiceState.load(state_dir, "gmail")
    report = reloaded.status()
    assert "gmail" in report
    assert "99999" in report or "5000" in report
