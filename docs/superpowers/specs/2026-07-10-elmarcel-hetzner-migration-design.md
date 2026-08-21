# elmarcel.com Migration to Hetzner — Design

**Created:** 2026-07-10
**Status:** Approved

## Goal

Serve elmarcel.com (the Hugo site currently hosted on DreamHost/DreamCompute at
173.236.200.12) from the already-provisioned Hetzner CX23 VPS, with HTTPS, so
DreamCompute can be cancelled afterwards.

Out of scope: bogartindustries.com (domain, webspace, email), domain transfers,
email of any kind, cancelling any subscription.

## Background / discovered state

- Site source: `/mnt/d/prg/bogartindustries_com_blog/pacifishticks` (repo name
  is legacy; the site lives at elmarcel.com). Hugo, theme in `layouts/`,
  pinned Hugo version **0.133.1** (`hugo_old.exe`).
- `config.toml` baseurl is `http://www.elmarcel.com/` — www is canonical; the
  live site has no HTTPS canonical URLs. `relativeURLs = false`, so the
  baseurl is baked into all absolute URLs, RSS, and sitemap at build time.
- **Source-tree defect:** the 87 MB photo gallery exists only in
  `public/images/gallery/` (build output). `static/images/` lacks it, though
  `generate_photo_posts.py` shows it originally lived in
  `static/images/gallery/`. A clean rebuild today would lose every photo.
- DNS: `elmarcel.com` and `www.elmarcel.com` → 173.236.200.12 (DreamHost).
- Hetzner CX23 is provisioned with SSH access, but no host/IP/key reference
  exists in the plum repo or `~/.ssh/config` — connection details must be
  supplied by the user into `.env` (keys `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
  already exist in `.env.example`).

## Architecture

One Docker Compose stack on the VPS at `/opt/elmarcel/`:

```
/opt/elmarcel/
├── docker-compose.yml     # versioned in plum: docker/elmarcel/
├── Caddyfile              # versioned in plum: docker/elmarcel/
├── src/                   # Hugo source, rsynced from workstation
└── site/                  # built output (docroot), atomically swapped
```

- Single service: `caddy:2-alpine`, ports 80, 443, 443/udp published.
- `./site` mounted read-only at `/srv`; named volumes `caddy_data` and
  `caddy_config` persist Let's Encrypt certificates.
- Caddyfile: `www.elmarcel.com` serves `/srv`; `elmarcel.com` 301-redirects to
  `https://www.elmarcel.com`. Automatic HTTPS (no certbot).
- The site is **built on the VPS** in a one-shot pinned container
  (`hugomods/hugo:0.133.1`); Docker is the only host dependency for both
  building and serving.

`/opt/<app>/` chosen over `/srv` or `/var/www`: the whole deployment (config,
source, output) stays one self-contained, OS-package-manager-free directory.

## Components

### 1. Source repair (one-time, in the blog repo)

Copy `public/images/gallery/` → `static/images/gallery/` and commit, making
the Hugo source self-contained and `public/` disposable build output.

### 2. `docker/elmarcel/` in plum

`docker-compose.yml` + `Caddyfile` as described above.

### 3. `scripts/deploy/deploy-elmarcel.sh` in plum

Uses `scripts/common/load-env.sh` (needs `VPS_HOST`, `VPS_USER`,
`VPS_SSH_KEY` in `.env`). Steps, each aborting loudly on failure or empty
output (no swallowed failures):

1. `rsync --delete` Hugo source (`content/`, `static/`, `layouts/`,
   `archetypes/`, `config.toml`) → `/opt/elmarcel/src/` (~97 MB first run,
   deltas after), plus the compose config → `/opt/elmarcel/`.
2. On the VPS: `docker run --rm hugomods/hugo:0.133.1` with `src/` mounted,
   building `--baseURL https://www.elmarcel.com/` into a staging dir, then
   atomically swap staging → `/opt/elmarcel/site` (a failed build never
   touches the live docroot).
3. `docker compose up -d` (no-op when Caddy already runs).
4. Verify with `curl --fail`: `/`, RSS feed, one deep blog post, one gallery
   image — asserting expected content in responses, not just HTTP 200.

### 4. One-time VPS prep (documented, run once)

Install Docker Engine + compose plugin if absent; open 80/443 (TCP) and
443 (UDP) in the Hetzner firewall.

## Cutover plan

1. Run deploy script; verify serving on the VPS via host-header/HTTP checks
   (Let's Encrypt cannot issue before DNS points at the VPS, so pre-cutover
   verification is HTTP-only).
2. User flips A records for `elmarcel.com` + `www.elmarcel.com` to the VPS IP
   at the current DNS provider (manual; lower TTL beforehand if high).
3. Caddy self-issues certificates within seconds of DNS propagating.
4. Post-cutover checks: HTTPS on www, apex→www redirect, HTTP→HTTPS redirect,
   RSS URLs are `https://www.elmarcel.com/...`, 404 page, gallery images.

**Rollback:** point A records back to 173.236.200.12. DreamHost stays
untouched until the user cancels it, so the old site remains a warm standby.

## Error handling

- Deploy script: `set -euo pipefail`, explicit check + abort with context on
  every remote step; never report success without the curl verification pass.
- Build failure leaves the live `site/` untouched (staging-dir swap).
- Cert issuance failure is visible via `docker compose logs caddy`; site
  still serves on HTTP 80 in that state.

## Testing

- Deploy script exercised against the plum `docker/` VPS-replica container
  first, then the real VPS.
- Post-cutover manual checks as listed in the cutover plan.
- Repo changes go through this worktree + feature branch + PR; pre-commit
  hooks (shellcheck, secrets) apply.

## Decisions log

| Decision | Choice | Alternatives rejected |
|----------|--------|----------------------|
| Scope | elmarcel.com live on Hetzner only | bogartindustries.com migration (dropped mid-brainstorm) |
| Web server | Caddy in Docker Compose | Caddy on host; nginx+certbot |
| Build location | On the VPS, pinned container | Local build + rsync of `public/` |
| Gallery fix | Restore to `static/` and commit | Rsync gallery as separate data |
| VPS layout | `/opt/elmarcel/` self-contained | `/srv`, `/var/www`, `~` |
| Canonical host | `www.elmarcel.com` (matches existing baseurl) | apex canonical |
