"""Google Contacts backup service — syncToken-based incremental."""

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


def _to_vcf(person: dict) -> str:
    """Convert a People API person resource to a minimal vCard string."""
    lines = ["BEGIN:VCARD", "VERSION:3.0"]

    names = person.get("names", [])
    if names:
        display_name = names[0].get("displayName", "")
        lines.append(f"FN:{display_name}")
        family = names[0].get("familyName", "")
        given = names[0].get("givenName", "")
        if family or given:
            lines.append(f"N:{family};{given};;;")

    for email in person.get("emailAddresses", []):
        lines.append(f"EMAIL:{email['value']}")

    for phone in person.get("phoneNumbers", []):
        lines.append(f"TEL:{phone['value']}")

    for org in person.get("organizations", []):
        name = org.get("name", "")
        title = org.get("title", "")
        if name:
            lines.append(f"ORG:{name}")
        if title:
            lines.append(f"TITLE:{title}")

    for addr in person.get("addresses", []):
        formatted = addr.get("formattedValue", "").replace("\n", "\\n")
        if formatted:
            lines.append(f"ADR:;;{formatted};;;;")

    lines.append("END:VCARD")
    return "\n".join(lines) + "\n"


@register
class ContactsService(BaseService):
    name = "contacts"
    scopes = ("https://www.googleapis.com/auth/contacts.readonly",)

    def sync(self, creds: Credentials, state: ServiceState, backup_dir: Path) -> SyncResult:
        start = time.time()
        service = build("people", "v1", credentials=creds)
        backup_dir.mkdir(parents=True, exist_ok=True)

        items_synced = 0
        items_failed = 0
        items_deleted = 0
        failed_ids: list[str] = []

        # Build list kwargs
        list_kwargs: dict = {
            "resourceName": "people/me",
            "personFields": "names,emailAddresses,phoneNumbers,organizations,addresses",
            "pageSize": 100,
            "requestSyncToken": True,
        }
        existing_token = state.data.get("sync_token")
        if existing_token:
            list_kwargs["syncToken"] = existing_token
        else:
            log.info("Full sync for contacts")

        # Paginate through all connections
        connections_resource = service.people().connections()
        request = connections_resource.list(**list_kwargs)
        next_sync_token = None

        while request:
            response = request.execute()
            next_sync_token = response.get("nextSyncToken", next_sync_token)
            connections = response.get("connections", [])

            for person in connections:
                resource_name = person.get("resourceName", "")
                person_id = resource_name.replace("people/", "")

                if not person_id:
                    continue

                # Check if deleted
                is_deleted = person.get("metadata", {}).get("deleted", False)

                try:
                    if is_deleted:
                        # Mark metadata as deleted, keep VCF
                        meta_path = backup_dir / f"{person_id}.json"
                        person["deleted"] = True
                        meta_path.write_text(
                            json.dumps(person, indent=2, ensure_ascii=False) + "\n"
                        )
                        items_deleted += 1
                        log.info("Contact deleted: %s", person_id)
                    else:
                        # Write VCF and metadata
                        (backup_dir / f"{person_id}.vcf").write_text(_to_vcf(person))
                        (backup_dir / f"{person_id}.json").write_text(
                            json.dumps(person, indent=2, ensure_ascii=False) + "\n"
                        )
                        items_synced += 1
                except Exception as e:
                    log.error("Failed to write contact %s: %s", person_id, e)
                    items_failed += 1
                    failed_ids.append(person_id)

            request = connections_resource.list_next(request, response)

        # Persist sync token (saved by cmd_sync after this returns)
        if next_sync_token:
            state.data["sync_token"] = next_sync_token

        elapsed = time.time() - start
        return SyncResult(
            service=self.name,
            items_synced=items_synced,
            items_failed=items_failed,
            items_deleted=items_deleted,
            failed_ids=failed_ids,
            elapsed_seconds=elapsed,
        )
