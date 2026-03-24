"""OAuth2 authentication for Google APIs."""

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

log = logging.getLogger(__name__)

# All read-only — the backup never modifies anything in the Google account.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class AuthManager:
    """Handles OAuth2 flow and credential storage."""

    SCOPES = SCOPES

    def __init__(self, client_secret_path: Path, state_dir: Path):
        self.client_secret_path = Path(client_secret_path)
        self.state_dir = Path(state_dir)
        self.token_path = self.state_dir / "token.json"

    def is_authorized(self) -> bool:
        """Check if a valid (or refreshable) token exists."""
        return self.token_path.exists()

    def authorize_interactive(self) -> Credentials:
        """Run the browser-based OAuth2 flow. Saves token to disk."""
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"Client secret not found at {self.client_secret_path}. "
                "Download it from Google Cloud Console and set GOOGLE_BACKUP_CLIENT_SECRET in .env"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secret_path),
            scopes=self.SCOPES,
        )
        creds = flow.run_local_server(port=0)
        self._save_token(creds)
        log.info("Authorization successful. Token saved to %s", self.token_path)
        return creds

    def get_credentials(self) -> Credentials:
        """Load credentials from disk, refreshing if needed."""
        if not self.token_path.exists():
            raise RuntimeError(
                "Not authorized. Run 'run.sh auth' first to complete the OAuth2 flow."
            )

        creds = Credentials.from_authorized_user_file(
            str(self.token_path), scopes=self.SCOPES
        )

        if creds.expired and creds.refresh_token:
            log.info("Access token expired, refreshing...")
            try:
                creds.refresh(Request())
                self._save_token(creds)
                log.info("Token refreshed successfully")
            except Exception as e:
                raise RuntimeError(
                    f"Token refresh failed: {e}. Re-run 'run.sh auth' to re-authorize."
                ) from e

        return creds

    def _save_token(self, creds: Credentials) -> None:
        """Persist credentials to disk."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
