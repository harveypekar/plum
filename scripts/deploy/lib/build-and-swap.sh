#!/bin/bash
# Build the elmarcel.com Hugo site and atomically swap it live.
# Runs entirely on the target host (VPS or a --local tmp dir) — the caller
# is responsible for getting the source onto the target before invoking this.
#
# Required env vars: TARGET_ROOT, SRC_DIR, HUGO_IMAGE, BASE_URL,
#                     GALLERY_MIN_FILES, GALLERY_SAMPLE_REL
# Usage: bash build-and-swap.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="build-and-swap"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../../common/logging.sh"

: "${TARGET_ROOT:?TARGET_ROOT must be set}"
: "${SRC_DIR:?SRC_DIR must be set}"
: "${HUGO_IMAGE:?HUGO_IMAGE must be set}"
: "${BASE_URL:?BASE_URL must be set}"
: "${GALLERY_MIN_FILES:?GALLERY_MIN_FILES must be set}"
: "${GALLERY_SAMPLE_REL:?GALLERY_SAMPLE_REL must be set}"

[ -d "$SRC_DIR/content" ] || log_die "Hugo source not found at $SRC_DIR"
[ -f "$SRC_DIR/config.toml" ] || log_die "config.toml missing in $SRC_DIR"
[ -d "$SRC_DIR/static/images/gallery" ] \
    || log_die "static/images/gallery missing in $SRC_DIR — run the gallery restore first"
[ -d "$TARGET_ROOT/www" ] || log_die "TARGET_ROOT/www missing — caller must create it before invoking this script"

log_info "Building site with $HUGO_IMAGE"
# SRC_DIR is NOT mounted :ro: Hugo writes a transient .hugo_build.lock into
# the source dir during the build and errors out on a read-only filesystem.
docker run --rm \
    -v "$SRC_DIR:/src" \
    -v "$TARGET_ROOT/www:/target" \
    "$HUGO_IMAGE" hugo \
    --source /src --destination /target/site.new \
    --baseURL "$BASE_URL" --cleanDestinationDir \
    || log_die "Hugo build failed; live site untouched"

test -f "$TARGET_ROOT/www/site.new/index.html" \
    || log_die "Build produced no index.html; live site untouched"

log_info "Atomically swapping site.new -> site"
(cd "$TARGET_ROOT/www" && rm -rf site.old \
    && { [ ! -d site ] || mv site site.old; } \
    && mv site.new site) \
    || log_die "Site swap failed"

log_info "Verifying built site"
test -f "$TARGET_ROOT/www/site/index.html" \
    || log_die "Build verification failed: www/site/index.html missing"
grep -qF 'https://www.elmarcel.com' "$TARGET_ROOT/www/site/index.xml" \
    || log_die "Build verification failed: RSS lacks https baseURL"
count="$(find "$TARGET_ROOT/www/site/images/gallery" -type f | wc -l)" \
    || log_die "Build verification failed: cannot count gallery files"
[ "$count" -ge "$GALLERY_MIN_FILES" ] \
    || log_die "Build verification failed: gallery has $count files, expected >= $GALLERY_MIN_FILES"
test -f "$TARGET_ROOT/www/site${GALLERY_SAMPLE_REL}" \
    || log_die "Build verification failed: sample gallery image missing"
log_info "Build verified: index.html present, https RSS, $count gallery files"
