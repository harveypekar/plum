"""Tests for Gmail backup service."""
import base64
import json
from unittest.mock import MagicMock, patch

from google_backup.services.gmail import GmailService
from google_backup.state import ServiceState


def _mock_gmail_api(messages, message_details, history=None, profile_history_id="99999"):
    """Build a mock Gmail API service."""
    service = MagicMock()

    # users().getProfile()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "historyId": profile_history_id,
    }

    # users().messages().list() — paginated
    list_mock = MagicMock()
    list_mock.execute.return_value = {
        "messages": [{"id": m} for m in messages],
        "resultSizeEstimate": len(messages),
    }
    service.users.return_value.messages.return_value.list.return_value = list_mock
    service.users.return_value.messages.return_value.list_next.return_value = None

    # users().messages().get()
    def _get_message(userId, id, format="raw"):
        mock = MagicMock()
        detail = message_details.get(id, {
            "id": id,
            "raw": base64.urlsafe_b64encode(b"From: test@test.com\nSubject: Test\n\nBody").decode(),
            "labelIds": ["INBOX"],
            "threadId": "thread1",
            "internalDate": "1711152000000",
        })
        mock.execute.return_value = detail
        return mock

    service.users.return_value.messages.return_value.get.side_effect = _get_message

    # users().history().list()
    if history is not None:
        hist_mock = MagicMock()
        hist_mock.execute.return_value = history
        service.users.return_value.history.return_value.list.return_value = hist_mock
        service.users.return_value.history.return_value.list_next.return_value = None

    return service


def test_gmail_full_sync(tmp_path):
    raw_email = base64.urlsafe_b64encode(
        b"From: alice@example.com\nSubject: Hello\n\nHi there"
    ).decode()

    messages = ["msg1", "msg2"]
    details = {
        "msg1": {
            "id": "msg1", "raw": raw_email,
            "labelIds": ["INBOX"], "threadId": "t1", "internalDate": "1711152000000",
        },
        "msg2": {
            "id": "msg2", "raw": raw_email,
            "labelIds": ["SENT"], "threadId": "t2", "internalDate": "1711152000000",
        },
    }

    mock_api = _mock_gmail_api(messages, details)
    state = ServiceState.load(tmp_path / "state", "gmail")

    with patch("google_backup.services.gmail.build", return_value=mock_api):
        svc = GmailService()
        result = svc.sync(MagicMock(), state, tmp_path / "gmail")

    assert result.items_synced == 2
    assert (tmp_path / "gmail" / "msg1" / "message.eml").exists()
    assert (tmp_path / "gmail" / "msg1" / "metadata.json").exists()
    assert (tmp_path / "gmail" / "msg2" / "message.eml").exists()

    meta = json.loads((tmp_path / "gmail" / "msg1" / "metadata.json").read_text())
    assert meta["labelIds"] == ["INBOX"]


def test_gmail_incremental_sync(tmp_path):
    """When historyId exists, use history API for incremental."""
    state = ServiceState.load(tmp_path / "state", "gmail")
    state.data["history_id"] = "10000"
    state.save()

    raw_email = base64.urlsafe_b64encode(b"From: new@example.com\nSubject: New\n\nNew msg").decode()

    history = {
        "history": [
            {"messagesAdded": [{"message": {"id": "msg_new"}}]},
        ],
        "historyId": "10001",
    }

    details = {
        "msg_new": {
            "id": "msg_new", "raw": raw_email,
            "labelIds": ["INBOX"], "threadId": "t3", "internalDate": "1711239000000",
        },
    }

    mock_api = _mock_gmail_api([], details, history=history)

    with patch("google_backup.services.gmail.build", return_value=mock_api):
        svc = GmailService()
        result = svc.sync(MagicMock(), state, tmp_path / "gmail")

    assert result.items_synced == 1
    assert (tmp_path / "gmail" / "msg_new" / "message.eml").exists()


def test_gmail_deletion_marks_metadata(tmp_path):
    """Deleted messages should have metadata marked, EML kept."""
    # Pre-existing message
    msg_dir = tmp_path / "gmail" / "msg_del"
    msg_dir.mkdir(parents=True)
    (msg_dir / "message.eml").write_text("From: old@test.com\nSubject: Old")
    (msg_dir / "metadata.json").write_text('{"id": "msg_del", "labelIds": ["INBOX"]}')

    state = ServiceState.load(tmp_path / "state", "gmail")
    state.data["history_id"] = "10000"
    state.save()

    history = {
        "history": [
            {"messagesDeleted": [{"message": {"id": "msg_del"}}]},
        ],
        "historyId": "10001",
    }

    mock_api = _mock_gmail_api([], {}, history=history)

    with patch("google_backup.services.gmail.build", return_value=mock_api):
        svc = GmailService()
        svc.sync(MagicMock(), state, tmp_path / "gmail")

    # EML should still exist
    assert (msg_dir / "message.eml").exists()
    # Metadata should show deleted
    meta = json.loads((msg_dir / "metadata.json").read_text())
    assert meta.get("deleted") is True
