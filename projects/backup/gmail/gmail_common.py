"""Shared auth and logging for Gmail backup tools."""

import json
import logging
import os
from datetime import date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCRIPT_DIR = Path(__file__).parent
LOG_BASE = os.path.expanduser("~/.logs/plum")

SCOPES_READONLY = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_MODIFY = ["https://www.googleapis.com/auth/gmail.modify"]


def setup_logging(script_name: str) -> logging.Logger:
    """Configure logging to file + stderr, matching plum conventions."""
    log_dir = Path(LOG_BASE) / script_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{date.today().isoformat()}.log"

    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_file)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def get_gmail_service(scopes: list[str] | None = None):
    """Authenticate and return a Gmail API service object.

    First run opens browser for OAuth consent. Subsequent runs use saved token.
    """
    if scopes is None:
        scopes = SCOPES_READONLY

    creds = None
    token_path = SCRIPT_DIR / "token.json"
    creds_path = SCRIPT_DIR / "credentials.json"

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {creds_path}. "
                    "Download OAuth2 credentials from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_data_dir() -> Path:
    """Return the data directory, creating it if needed."""
    d = SCRIPT_DIR / "data"
    d.mkdir(exist_ok=True)
    return d


def get_reports_dir() -> Path:
    """Return the reports directory, creating it if needed."""
    d = SCRIPT_DIR / "reports"
    d.mkdir(exist_ok=True)
    return d


def load_metadata() -> dict:
    """Load metadata.json or return empty default."""
    meta_path = get_data_dir() / "metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return {"history_id": None, "message_count": 0, "messages": {}}


def save_metadata(metadata: dict):
    """Save metadata.json."""
    meta_path = get_data_dir() / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
