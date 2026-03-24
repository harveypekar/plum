"""Tests for Google Contacts backup service."""
import json
from unittest.mock import MagicMock, patch

from google_backup.services.contacts import ContactsService
from google_backup.state import ServiceState


def _mock_people_api(connections, next_sync_token="sync_abc"):
    """Build a mock People API service."""
    service = MagicMock()

    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "connections": connections,
        "nextSyncToken": next_sync_token,
        "totalPeople": len(connections),
    }

    service.people.return_value.connections.return_value.list.return_value = mock_list
    # Pagination termination on the resource, not the request
    service.people.return_value.connections.return_value.list_next.return_value = None
    return service


def test_contacts_full_sync(tmp_path):
    connections = [
        {
            "resourceName": "people/c123",
            "names": [{"displayName": "Alice Smith"}],
            "emailAddresses": [{"value": "alice@example.com"}],
        },
        {
            "resourceName": "people/c456",
            "names": [{"displayName": "Bob Jones"}],
        },
    ]

    mock_api = _mock_people_api(connections)
    state = ServiceState.load(tmp_path / "state", "contacts")

    with patch("google_backup.services.contacts.build", return_value=mock_api):
        svc = ContactsService()
        result = svc.sync(MagicMock(), state, tmp_path / "contacts")

    assert result.items_synced == 2
    assert (tmp_path / "contacts" / "c123.vcf").exists()
    assert (tmp_path / "contacts" / "c123.json").exists()

    vcf_content = (tmp_path / "contacts" / "c123.vcf").read_text()
    assert "Alice Smith" in vcf_content
    assert "alice@example.com" in vcf_content


def test_contacts_deleted_contact(tmp_path):
    """Deleted contacts should have metadata marked but VCF kept."""
    # Pre-existing contact
    backup_dir = tmp_path / "contacts"
    backup_dir.mkdir(parents=True)
    (backup_dir / "c789.vcf").write_text("BEGIN:VCARD\nFN:Old Contact\nEND:VCARD")
    (backup_dir / "c789.json").write_text('{"resourceName": "people/c789"}')

    connections = [
        {
            "resourceName": "people/c789",
            "metadata": {"deleted": True},
        },
    ]
    mock_api = _mock_people_api(connections)
    state = ServiceState.load(tmp_path / "state", "contacts")

    with patch("google_backup.services.contacts.build", return_value=mock_api):
        svc = ContactsService()
        svc.sync(MagicMock(), state, backup_dir)

    # VCF should still exist
    assert (backup_dir / "c789.vcf").exists()
    # Metadata should show deleted
    data = json.loads((backup_dir / "c789.json").read_text())
    assert data.get("deleted") is True
