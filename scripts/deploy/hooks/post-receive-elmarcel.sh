#!/bin/bash
# post-receive hook for the elmarcel.com blog bare repo.
# Installed at /opt/elmarcel/repo.git/hooks/post-receive on the VPS.
# Git invokes this automatically after `git push`, with pushed refs on stdin
# as lines of "<old-sha> <new-sha> <ref-name>". Only refs/heads/master
# triggers a rebuild.

set -euo pipefail

REPO_ROOT="/opt/elmarcel"
WORK_TREE="$REPO_ROOT/src"
GIT_DIR_PATH="$REPO_ROOT/repo.git"

while read -r _old_sha new_sha ref_name; do
    if [ "$ref_name" != "refs/heads/master" ]; then
        echo "post-receive: ignoring push to $ref_name (only master triggers a deploy)"
        continue
    fi

    echo "post-receive: deploying $new_sha"
    mkdir -p "$WORK_TREE"
    if ! GIT_DIR="$GIT_DIR_PATH" GIT_WORK_TREE="$WORK_TREE" git checkout -f "$new_sha"; then
        echo "post-receive: checkout failed; live site untouched" >&2
        exit 1
    fi

    SITE_SRC="$WORK_TREE/pacifishticks"
    if ! TARGET_ROOT="$REPO_ROOT" SRC_DIR="$SITE_SRC" \
        HUGO_IMAGE="hugomods/hugo:0.133.1" \
        BASE_URL="https://www.elmarcel.com/blog/" \
        GALLERY_MIN_FILES=118 \
        GALLERY_SAMPLE_REL="/images/gallery/2004_01_03_13_35_42_4138319335.jpg" \
        LOG_VERBOSE=true \
        bash "$REPO_ROOT/deploy/lib/build-and-swap.sh"; then
        # build-and-swap.sh swaps site.new -> site BEFORE running its own
        # post-swap verification, so a failure here does not necessarily mean
        # the live site is untouched — it may already have been swapped to a
        # broken/incomplete build. Do not claim otherwise.
        echo "post-receive: build/swap failed — site may or may not have been swapped; check target log (see below)" >&2
        echo "post-receive: see ~/.logs/plum/build-and-swap/ on the VPS for full detail" >&2
        exit 1
    fi

    echo "post-receive: deploy complete"

    if ! rclone sync "$GIT_DIR_PATH" hetzner-crypt:bak/elmarcel-blog-repo; then
        echo "post-receive: WARNING backup to Storage Box failed (deploy already succeeded)" >&2
        # Do not fail the push over a backup failure — the site update already
        # happened. Surface it loudly so the user notices and can re-run it.
    fi
done
