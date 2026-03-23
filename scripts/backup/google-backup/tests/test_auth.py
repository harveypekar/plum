"""Tests for OAuth2 auth module."""
import json

from google_backup.auth import AuthManager


def test_all_scopes_are_readonly():
    for scope in AuthManager.SCOPES:
        assert "readonly" in scope, f"Scope is not read-only: {scope}"


def test_all_scopes_use_full_uri():
    for scope in AuthManager.SCOPES:
        assert scope.startswith("https://"), f"Scope must use full URI: {scope}"


def test_token_path(tmp_path):
    manager = AuthManager(
        client_secret_path=tmp_path / "secret.json",
        state_dir=tmp_path / "state",
    )
    assert manager.token_path == tmp_path / "state" / "token.json"


def test_is_authorized_false_when_no_token(tmp_path):
    manager = AuthManager(
        client_secret_path=tmp_path / "secret.json",
        state_dir=tmp_path / "state",
    )
    assert manager.is_authorized() is False


def test_is_authorized_true_when_valid_token_exists(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    # Write a minimal token file
    token_data = {
        "token": "access_token_123",
        "refresh_token": "refresh_token_456",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "test_secret",
        "scopes": AuthManager.SCOPES,
    }
    (state_dir / "token.json").write_text(json.dumps(token_data))

    manager = AuthManager(
        client_secret_path=tmp_path / "secret.json",
        state_dir=state_dir,
    )
    assert manager.is_authorized() is True
