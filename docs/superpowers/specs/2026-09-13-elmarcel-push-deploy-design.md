# elmarcel.com: push-to-deploy for blog posts — Design

**Context:** the elmarcel.com Hetzner migration (PR #203, #204, both merged) and the
`/blog` subpath change are live. Today, publishing a new post means manually
running `deploy-elmarcel.sh` from a workstation, which rsyncs the Hugo source
from the local checkout to the VPS. The user wants a simpler loop: write a
post, `git push`, and the VPS rebuilds and serves it automatically — no manual
deploy step for content changes.

## Problem

The blog repo (`bogartindustries_com_blog`) has no live remote — its only
configured remote is the old DreamHost SSH host, which is unreachable now that
DNS/nameservers moved to Hover as part of this same migration, and the user
intends to close the DreamHost account entirely. A hosting location and a
publish mechanism both need to exist before push-to-deploy is possible.

## Decisions (confirmed with user)

- **Hosting:** a bare git repo on the Hetzner VPS itself
  (`/opt/elmarcel/repo.git`), not GitHub. The user's workstation checkout adds
  it as a second remote and pushes there directly over SSH.
- **Trigger:** a `post-receive` hook in that bare repo — not polling, not
  GitHub Actions (there's no GitHub involved in this design).
- **Backup:** not GitHub-as-backup. The user already has an encrypted
  Hetzner Storage Box backup pipeline (`plum/projects/backup/sync-dirs.py` +
  `backup-dirs.json`, enforced `type=crypt` remote per
  `.claude/rules/backup.md`). That tool syncs *local* directories from the
  workstation to the Storage Box — it can't reach data that only exists on the
  VPS. Since the bare repo lives on the VPS, the backup step runs there too:
  an `rclone sync` of `/opt/elmarcel/repo.git` to the same `hetzner-crypt`
  remote, added to the end of the `post-receive` hook (push frequency is low —
  new blog posts — so a synchronous step needs no separate cron schedule).
  This requires one-time setup: install `rclone` and the `hetzner-crypt`
  remote config on the VPS (currently only present on the workstation).

## Architecture

```
workstation                      VPS (77.42.80.52)
─────────────                    ─────────────────
pacifishticks/  --git push-->    /opt/elmarcel/repo.git (bare)
                                        │
                                        ▼ post-receive hook
                                  checkout pushed commit --> /opt/elmarcel/src
                                        │
                                        ▼ (reused from deploy-elmarcel.sh)
                                  hugomods/hugo:0.133.1 build --> site.new
                                        │
                                        ▼
                                  atomic swap site.new -> site
                                        │
                                        ▼
                                  rclone sync repo.git -> hetzner-crypt:bak/elmarcel-blog-repo
```

Caddy itself needs no restart — it already serves out of the parent `www/`
mount (from the original migration design), so the atomic swap is visible
immediately, exactly as it is today with the manual deploy script.

## What changes vs. what's reused

- **New:** the bare repo on the VPS, the `post-receive` hook script, one-time
  `rclone`/`hetzner-crypt` setup on the VPS.
- **Reused, not rewritten:** the build (pinned Hugo container into
  `site.new`), the atomic swap, and the build-verification logic
  (`verify_build` in `deploy-elmarcel.sh`) — the hook calls the same logic
  rather than duplicating it, likely by factoring the "build + swap + verify"
  portion of `deploy-elmarcel.sh` into a shared script both the hook and the
  manual deploy path can call.
- **Unchanged:** `deploy-elmarcel.sh` keeps handling infrastructure changes —
  Caddyfile or compose updates that live in the `plum` repo. Push-to-deploy is
  scoped to blog *content* only; it does not rsync `docker/elmarcel/` files.

## Error handling

- If the Hugo build fails on push, the hook must abort before the swap (same
  guarantee `deploy-elmarcel.sh` already has: "Hugo build failed on target;
  live site untouched") and report the failure back to the pusher's terminal
  (git shows `post-receive` hook stderr/stdout to the client automatically).
- If the `rclone` backup step fails, it should not block or roll back the
  already-completed deploy — the site update and the backup are independent
  concerns; log the backup failure clearly but let the push succeed.

## Testing

- Push a trivial content change and confirm: the hook fires, the build
  succeeds, the change is live (checked directly against the VPS, forced-IP
  curl, same verification approach used throughout this migration), and the
  Storage Box backup received the new commit.
- Push a deliberately broken build (e.g. malformed front matter) and confirm
  the hook aborts cleanly, the live site is untouched, and the failure is
  visible in the pusher's terminal.
