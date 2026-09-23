---
paths:
  - "projects/garmin/**"
  - "docker/garmin/**"
---

# Garmin Data Source

Standalone Hetzner-hosted project: scheduled Garmin Connect fetcher + a
password-protected dev browse page. Deployed at `garmin.elmarcel.com`,
behind the existing elmarcel Caddy instance.

## Commands

```bash
cd projects/garmin
source .venv/bin/activate
python fetch_garmin.py            # manual fetch (incremental)
python fetch_garmin.py --full     # force re-fetch everything
uvicorn app:app --reload          # run the dev browse page locally

pytest tests/                     # Python tests
bash tests/test_backup_garmin.sh  # backup script test
```

## Architecture

- File-based storage only — no database. `fetch_garmin.py` writes the same
  raw JSON tree it always has (`data/garmin/{activities,daily,weekly,
  profile,devices,gear,goals,badges,challenges,workouts,blood_pressure,
  weight,progress}/`); `app.py` is a thin FastAPI browser over that tree,
  nothing more.
- `sync_lock.py` (fcntl-based) prevents cron and a manual "Sync now" click
  from ever running two fetches at once.
- `status.json` (written after every fetch run) is the only thing the
  dashboard reads to show sync health — never silently swallow a failed run.
- Auth: `GARMIN_EMAIL`/`GARMIN_PASSWORD` env vars for unattended login; if
  the account has MFA, the first login must be run interactively once
  (e.g. over SSH with a TTY) to establish the cached garth token.
- Access control is entirely at the Caddy layer (`basicauth` in
  `docker/elmarcel/Caddyfile`) — no app-level auth code.

## Deployment

- `scripts/deploy/setup-garmin-vps.sh` — one-time: creates the shared
  `edge` Docker network, `/opt/garmin/` on the VPS, reminds about the
  manual rclone config copy.
- `scripts/deploy/deploy-garmin.sh` — rsyncs the project + compose config,
  builds, hashes `GARMIN_WEB_PASSWORD` into the Caddyfile's basicauth,
  refreshes the elmarcel Caddy stack, verifies via `curl --fail`.

## Backup

`backup_garmin.sh` runs daily from the `garmin-cron` container: zips
`data/garmin/`, uploads to `hetzner-crypt:bak/garmin/`, keeps the newest 3.
Aborts loudly if the configured rclone remote isn't type `crypt` — see
`.claude/rules/backup.md` (non-negotiable).
