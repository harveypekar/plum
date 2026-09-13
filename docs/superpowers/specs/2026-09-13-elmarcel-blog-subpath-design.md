# elmarcel.com: serve the blog under /blog — Design

**Context:** the elmarcel.com Hetzner migration (PR #203, merged) serves the Hugo
site at `https://www.elmarcel.com/` root. Before running the real deployment,
the user asked to change the URL scheme: the whole site should live under
`/blog`, with the bare root 301-redirecting there. No particular reason beyond
preference; no other content is planned for root or other subpaths.

## Problem

Hugo's content already has a section literally named `blog` for posts
(`content/blog/` → `/blog/2008_.../`). Putting the *whole site* under a URL
prefix also named `/blog` would double it: `/blog/blog/2008_.../`. Decision:
rename the content section to `posts`, so posts read as `/blog/posts/2008_.../`.

## Approach

Change Hugo's `baseURL` to `https://www.elmarcel.com/blog/` at build time (already
parameterized in `deploy-elmarcel.sh`) and have Caddy serve the built site under
a `/blog` path prefix (`handle_path`, which strips the prefix before hitting the
docroot). Rejected alternative: keep baseURL at root and just relocate the built
files under `www/site/blog/` — internal absolute links generated via
`{{.Site.BaseURL}}` would still point at root (e.g. `/main.css`), breaking CSS/JS/
RSS once the files move. Hugo's own baseURL mechanism is the correct way to
deploy under a subpath; verified every template's link generation (see below).

## Changes — blog repo (`bogartindustries_com_blog/pacifishticks`)

- Rename `content/blog/` → `content/posts/`. Verified no internal content links
  reference `/blog/` as a relative path — the only `/blog/` occurrences in post
  bodies are dead absolute links to the old `bogartindustries.com` WordPress
  domain, unaffected by this rename.
- `config.toml`: menu entries currently hardcode absolute urls (`/blog/`, `/tech/`,
  `/photo/`). Hugo does **not** auto-prefix a menu `url` that already starts with
  `/` — unlike page-relative links, it's taken literally. Update to
  `/blog/posts/`, `/blog/tech/`, `/blog/photo/` (identifier for the renamed
  section becomes `posts`; display name can stay "blog").
- `layouts/index.html`: RSS link hardcodes `{{.Site.BaseURL}}blog/index.xml` →
  change `blog` to `posts`. Every other link in the theme already uses
  `{{.Site.BaseURL}}` (checked `index.html`, `header.html`, `body_top.html`,
  `_default/list.html`), which will already carry the new `/blog/` prefix once
  baseURL changes — no other template edits needed.
- Gallery images use relative markdown links (`../images/gallery/...`) — resolve
  correctly under the new prefix automatically, no changes needed.

## Changes — plum repo (this worktree)

- `scripts/deploy/deploy-elmarcel.sh`:
  - `BASE_URL` → `https://www.elmarcel.com/blog/`
  - `DEEP_POST_PATH` → `/blog/posts/2008_10_19_6_changelog/`
  - `SAMPLE_IMAGE_PATH` → `/blog/images/gallery/2004_01_03_13_35_42_4138319335.jpg`
  - `run_check()`'s home-content check must hit `https://<host>/blog/` directly
    (checking bare `/` would only see a 301 redirect body, not site content) —
    keep a separate `curl_expect` for bare `/` → 301 → `/blog/`.
- `docker/elmarcel/Caddyfile`:
  - `www.elmarcel.com` block: redirect bare `/` → `/blog/` (301) and bare
    `/blog` (no trailing slash) → `/blog/` (301); serve everything else under
    `/blog/*` via `handle_path` (strips the prefix) rooted at `/srv/site`.
  - `elmarcel.com` (apex) block unchanged — still 301s to
    `https://www.elmarcel.com{uri}`.

## Known tradeoff

This permanently changes post URLs (`/blog/2008.../` → `/blog/posts/2008.../`).
Acceptable because DNS hasn't cut over yet — nothing is publicly live on the new
host under the old scheme, so there's no live redirect-migration concern. We're
defining the URL scheme before launch, not changing one that's already serving
traffic.

## Testing

Same local pipeline as the original migration: `deploy-elmarcel.sh --local`
followed by the Task-5-style Caddy smoke test (scratch compose stack on
:8088), re-run against the new `/blog` paths — home page content at `/blog/`,
deep post at `/blog/posts/2008_10_19_6_changelog/`, sample gallery image, and a
404 for an unknown path. Root `/` and `/blog` redirect checks added to the
smoke test since they're new behavior.
