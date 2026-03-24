"""CLI entry point: python -m google_backup [auth|--all|--gmail|...]."""

import argparse
import logging
import os
import sys
from pathlib import Path

from google_backup.auth import AuthManager
from google_backup.services import get_all
from google_backup.state import ServiceState

log = logging.getLogger("google_backup")

SERVICE_NAMES = ["gmail", "calendar", "contacts", "drive", "tasks", "youtube"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="google-backup",
        description="Incremental backup of Google account data.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("auth", help="Run OAuth2 authorization flow (opens browser)")

    # Default command is "sync" (no subcommand needed)
    parser.set_defaults(command="sync")

    parser.add_argument("--all", action="store_true", help="Backup all services")
    parser.add_argument("--status", action="store_true", help="Show sync status and exit")
    for name in SERVICE_NAMES:
        parser.add_argument(f"--{name}", action="store_true", help=f"Backup {name}")

    return parser.parse_args(argv)


def setup_logging() -> None:
    """Configure Python logging to write to LOG_FILE (from bash wrapper) and console."""
    log.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    log.addHandler(console)

    log_file = os.environ.get("LOG_FILE")
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(fh)


def get_config() -> tuple[Path, Path]:
    """Read config from env variables. Returns (client_secret_path, backup_dir)."""
    client_secret = os.environ.get("GOOGLE_BACKUP_CLIENT_SECRET")
    if not client_secret:
        log.error("GOOGLE_BACKUP_CLIENT_SECRET not set in .env")
        sys.exit(1)

    backup_dir = os.environ.get("GOOGLE_BACKUP_DIR")
    if not backup_dir:
        log.error("GOOGLE_BACKUP_DIR not set in .env")
        sys.exit(1)

    return Path(client_secret).expanduser(), Path(backup_dir).expanduser()


def resolve_services(args: argparse.Namespace) -> list[str]:
    """Determine which services to run based on CLI args."""
    if args.all:
        return SERVICE_NAMES
    selected = [name for name in SERVICE_NAMES if getattr(args, name, False)]
    if not selected:
        log.error("No services selected. Use --all or --gmail, --calendar, etc.")
        sys.exit(1)
    return selected


def cmd_status(backup_dir: Path) -> None:
    """Print sync status for all services and exit."""
    state_dir = backup_dir / "state"
    for name in SERVICE_NAMES:
        state = ServiceState.load(state_dir, name)
        print(state.status())


def cmd_auth(client_secret: Path, backup_dir: Path) -> None:
    """Run interactive OAuth2 flow."""
    auth = AuthManager(client_secret, backup_dir / "state")
    auth.authorize_interactive()
    print("Authorization complete.")


def cmd_sync(client_secret: Path, backup_dir: Path, service_names: list[str]) -> int:
    """Run sync for selected services. Returns exit code."""
    auth = AuthManager(client_secret, backup_dir / "state")
    creds = auth.get_credentials()
    state_dir = backup_dir / "state"

    registry = get_all()
    any_errors = False

    for name in service_names:
        if name not in registry:
            log.warning("Service '%s' not yet implemented, skipping", name)
            continue

        service_cls = registry[name]
        service = service_cls()
        state = ServiceState.load(state_dir, name)
        service_backup_dir = backup_dir / name

        log.info("Starting sync: %s", name)
        # Pass state INTO sync — service mutates it with sync tokens/historyIds
        result = service.sync(creds, state, service_backup_dir)
        log.info(result.summary())

        if result.has_errors:
            any_errors = True

        # Save state (with sync tokens set by service + updated item count)
        state.data["items_backed_up"] = result.items_synced
        state.clear_partial_cursor()
        state.save()

    return 1 if any_errors else 0


def main() -> None:
    setup_logging()
    args = parse_args()

    if args.command == "auth":
        client_secret, backup_dir = get_config()
        cmd_auth(client_secret, backup_dir)
        return

    if args.status:
        _, backup_dir = get_config()
        cmd_status(backup_dir)
        return

    client_secret, backup_dir = get_config()
    service_names = resolve_services(args)
    exit_code = cmd_sync(client_secret, backup_dir, service_names)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
