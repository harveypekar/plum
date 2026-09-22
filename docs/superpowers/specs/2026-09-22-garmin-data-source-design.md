# Garmin Data Source — Design

**Created:** 2026-09-22
**Status:** Approved

## Goal

A standalone project that pulls all available data from Garmin Connect,
stores it, auto-refreshes on a schedule, and exposes a password-protected
dev/debug web page to browse everything fetched — every field, no
interpretation layer. Deployed as its own Docker stack on the Hetzner VPS,
reachable at `garmin.elmarcel.com`.

Out of scope: `projects/coach` (getting its own rewrite, not touched here),
any analysis/charting of the data, Garmin's official partner Health API
(push/webhook) — that requires a business partnership and per-user OAuth
consent flow, not viable for a personal project; polling via the existing
unofficial `garminconnect`/`garth` login is the only realistic option.

## Background / discovered state

- `projects/coach/fetch_garmin.py` (626 lines) already fetches essentially
  every Garmin Connect endpoint into a JSON file tree, with incremental
  re-fetch detection and retry/backoff. `garmin_loader.py` parses a subset
  of that tree for coach's running-analysis needs. Both currently run
  manually on the local WSL2 machine; auth is an interactive `getpass`
  prompt with the garth session token cached to `data/garmin/.tokens/`.
- `projects/db/schema.sql` has a `garmin_activities` table (typed columns +
  a `raw JSONB` column) but only models activities — none of the dozens of
  other endpoint categories (daily wellness, weekly aggregates, profile,
  devices, gear, goals, badges, challenges, workouts, blood pressure,
  weight, progress). Not used by this project (see Data Storage below).
- The Hetzner CX23 VPS currently runs one Docker Compose stack,
  `docker/elmarcel/`, with a single Caddy instance bound to ports 80/443
  serving `www.elmarcel.com`. No shared reverse-proxy network exists yet
  for a second app.
- A prior commit installed the `rclone` binary on the VPS (for elmarcel
  blog-repo backups) but explicitly did not copy the rclone config, since
  it holds real credentials — the VPS has no working `hetzner-crypt:`
  remote yet. This project has the same prerequisite.
- `.claude/rules/backup.md` (non-negotiable): all data sent to Hetzner
  Storage Box must go through the `hetzner-crypt:` remote, never the bare
  `hetzner:` remote; any backup script must verify the remote resolves to
  a `crypt` backend before transferring.

## Data Storage: file-based, no database

Three approaches were considered:

| Approach | Verdict |
|---|---|
| **File-based JSON tree (chosen)** | Keep the exact file layout `fetch_garmin.py` already produces. The web page is a thin browser over that tree. Every field is exposed by construction — nothing to model, nothing to fall out of sync with Garmin's API. No DB infra to run/back up/migrate. |
| Postgres document store (JSONB blobs) | Same "expose everything" property, but adds a Postgres container, connection handling, backup/migration surface for a page whose only job is dev-debugging. Rejected: infra cost with no matching benefit. |
| Structured schema (extend `garmin_activities`-style typed tables) | Rejected: only covers activities today; modeling dozens of other endpoint types is large effort, and typed columns actively fight "expose all fields" — anything not anticipated gets silently dropped. |

## Architecture

New top-level project `projects/garmin/`:

```
projects/garmin/
├── fetch_garmin.py      # moved from projects/coach/, adapted (see Data Flow)
├── app.py                # FastAPI web app
├── Dockerfile
├── requirements.txt
├── tests/
└── data/garmin/          # gitignored; JSON tree, same layout as today
```

New `docker/garmin/docker-compose.yml`, two services sharing a named
volume `garmin_data` (mounted at `data/garmin/` in both):

- `garmin-web` — uvicorn/FastAPI: status dashboard, JSON tree browser,
  `/sync` endpoint to trigger a fetch on demand.
- `garmin-cron` — same image, cron fires `fetch_garmin.py` every 4 hours
  (`0 */4 * * *`), plus a daily backup job (see Backup).

**Caddy integration:** one Caddy instance already owns 80/443 for
elmarcel. Rather than a second Caddy, add a new site block to the
*existing* `docker/elmarcel/Caddyfile`:

```
garmin.elmarcel.com {
	basicauth {
		<user> <bcrypt-hash>
	}
	reverse_proxy garmin-web:8000
}
```

This requires both compose stacks to join a shared external Docker
network (`edge`), created once on the VPS (`docker network create edge`)
and referenced as `external: true` in both compose files. This is the one
piece of existing elmarcel infra this project touches.

The bcrypt hash in the Caddyfile is generated at deploy time from
`GARMIN_WEB_PASSWORD` (via `caddy hash-password`) by
`deploy-garmin.sh`/`deploy-elmarcel.sh` tooling — the plaintext password
itself only ever lives in `.env`, never committed.

## Data Flow, Auth, Scheduling

- **Auth:** `.env` on the VPS gets `GARMIN_EMAIL` / `GARMIN_PASSWORD`
  (never committed). When no cached token exists, the script logs in with
  these instead of the current interactive `getpass` prompt. The garth
  session token is cached to `data/garmin/.tokens/` and auto-refreshes on
  later runs, same mechanism as today.
- **MFA caveat:** if the Garmin account has MFA enabled, the first
  headless login can't complete — requires one interactive run (e.g. SSH
  with a TTY) to establish the cached token. If the token later expires
  or is invalidated, the scheduled run fails loudly and needs one more
  interactive re-auth. This is a documented limitation, not solved here.
- **Backfill:** first run does the full historical fetch (existing
  behavior); every run after is incremental, using the detection logic
  already in `fetch_garmin.py`.
- **Manual sync:** the web page's "Sync now" button calls `/sync` on
  `garmin-web`, which runs the fetch as a background task. A lockfile
  (`data/garmin/.sync.lock`) prevents cron and a manual trigger from
  overlapping; if one is already running, the other reports "sync in
  progress" instead of double-firing.
- **Status visibility:** the fetch script writes `status.json` after
  every run (last run time, success/failure, per-category counts, last
  error text). The web page reads this. Failures are surfaced, never
  swallowed, per the project's debugging rules.

## Web Page

FastAPI, behind Caddy `basicauth` (single shared credential in `.env`,
key `GARMIN_WEB_PASSWORD`):

- `/` — status dashboard: last sync time/result, record counts per
  category, "Sync now" button.
- `/browse/{category}` and `/browse/{category}/{id_or_date}` — navigable
  tree mirroring the JSON layout (activities, daily, weekly, profile,
  devices, gear, goals, badges, challenges, workouts, blood_pressure,
  weight, progress).
- Individual file view — raw pretty-printed JSON, every field visible, no
  formatting/interpretation layer. This is a dev tool, not a consumer UI.

## Backup

Garmin data lives on the VPS, not the local machine, so this backup runs
from the VPS — unlike the existing photo/music/ref/books backups, which
sync local Windows folders to Hetzner Storage Box.

- Bundled into the `garmin-cron` container (already has cron + volume
  access): daily job zips the `garmin_data` volume into
  `bak_garmin_<date>.zip`.
- Uploads via `rclone copy` to `hetzner-crypt:bak/garmin/` — sitting next
  to the existing `bak/music/` on Hetzner Storage Box.
- Before every upload, verifies the configured remote actually resolves
  to a `crypt` backend and aborts loudly if not (mirrors the
  `require_encrypted_remote` check in `projects/backup/backup-dirs.json`).
- After a successful upload, deletes anything beyond the newest 3 zips in
  that remote folder (rolling retention of 3).
- **Manual prerequisite:** the user must copy their rclone config
  (containing `hetzner-crypt` credentials) onto the VPS, e.g. to
  `/opt/garmin/rclone.conf`, bind-mounted read-only into `garmin-cron`.
  Not automated — same precedent as the elmarcel rclone install, which
  explicitly left credential placement to a manual, confirmed step.

## Deployment

- New `.env` keys (added as empty placeholders to `.env.example`):
  `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMIN_WEB_PASSWORD`.
- `scripts/deploy/deploy-garmin.sh`, mirroring `deploy-elmarcel.sh`:
  rsync project + compose config to `/opt/garmin/`, `docker compose up -d
  --build`, verify via `curl --fail` through basic auth against `/`.
- One-time VPS prep (documented, run once): create the shared `edge`
  Docker network; copy rclone config for the backup job.

## Error Handling

- Fetch script: per-endpoint failures logged and skipped (existing
  behavior), overall run status always written to `status.json` — never
  a silent empty result.
- Sync lockfile prevents concurrent fetch runs (cron vs. manual button).
- Backup script aborts loudly (non-zero exit, clear message) if the
  remote isn't `hetzner-crypt`, if the zip step fails, or if the upload
  fails — never proceeds partially.
- `deploy-garmin.sh`: `set -euo pipefail`, explicit checks with context
  on every remote step, never reports success without the curl
  verification pass.

## Testing

- pytest for the adapted fetch script: unattended auth path, lockfile
  behavior, `status.json` writing — extends the existing
  `test_garmin_loader.py` pattern.
- Manual verification after deploy: trigger sync via the button, confirm
  data appears in the browse UI, confirm cron fires (container logs),
  confirm basicauth blocks unauthenticated requests, confirm a backup
  run produces a zip in `hetzner-crypt:bak/garmin/` and prunes to 3.

## Decisions Log

| Decision | Choice | Alternatives rejected |
|---|---|---|
| Reuse existing fetch code | Move + adapt `fetch_garmin.py`/`garmin_loader.py` from `projects/coach` | Clean rewrite; leave coach untouched and duplicate logic |
| Data storage | File-based JSON tree, no DB | Postgres JSONB document store; structured typed schema |
| Web page scope | Status + raw browsable data, all fields, dev-only | Add charts/analysis; status-only with no browsing |
| Web access control | Caddy basicauth, single shared credential | Public, no auth; VPN/IP allowlist |
| Pull interval | Every 3-4 hours via cron, plus manual "Sync now" button | Hourly; daily |
| Garmin data freshness mechanism | Polling (unofficial `garminconnect`/`garth` login) | Official Health API push/webhook (requires business partnership, per-user OAuth consent) |
| Subdomain | `garmin.elmarcel.com`, new Caddy site block on existing instance | `data.elmarcel.com`; separate Caddy instance (port conflict) |
| Backup mechanism | VPS-side zip + rolling-3 retention via `garmin-cron`'s cron, uploaded to `hetzner-crypt:bak/garmin/` | Add to `backup-dirs.json`'s local-machine directory-sync model (wrong shape: that syncs raw dirs from Windows, this needs a VPS-side zip+retention job) |
