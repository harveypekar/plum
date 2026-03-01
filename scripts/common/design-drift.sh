#!/bin/bash
# Design Drift Detection Helper
# Scans git commits since the last design-checked-* tag and outputs
# a structured markdown drift report to stdout.
#
# Usage: bash scripts/common/design-drift.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# --- Find the most recent design-checked-* tag ---
LATEST_TAG=$(git tag -l 'design-checked-*' --sort=-creatordate | head -n 1)

if [ -n "$LATEST_TAG" ]; then
    SINCE_REF="$LATEST_TAG"
    SINCE_LABEL="\`${LATEST_TAG}\`"
else
    SINCE_REF=""
    SINCE_LABEL="all commits"
fi

# --- Header ---
echo "## Design Drift Report"
echo ""
echo "**Analyzing commits since:** ${SINCE_LABEL}"
echo ""

# --- Commit History with Diffs ---
echo "## Commit History with Diffs"
echo ""

# Build the commit range for git log / git show
if [ -n "$SINCE_REF" ]; then
    COMMIT_RANGE="${SINCE_REF}..HEAD"
else
    COMMIT_RANGE="HEAD"
fi

# Collect commit hashes oldest-to-newest
if [ -n "$SINCE_REF" ]; then
    COMMITS=$(git log --reverse --format='%h' "${COMMIT_RANGE}")
else
    COMMITS=$(git log --reverse --format='%h')
fi

if [ -z "$COMMITS" ]; then
    echo "_No commits found._"
    echo ""
else
    while IFS= read -r SHORT_HASH; do
        MESSAGE=$(git log -1 --format='%s' "$SHORT_HASH")
        DATE=$(git log -1 --format='%ai' "$SHORT_HASH")

        echo "### Commit \`${SHORT_HASH}\`: ${MESSAGE}"
        echo "**Date:** ${DATE}"
        echo ""

        echo "**Files changed:**"
        echo "\`\`\`"
        git show --stat --format='' "$SHORT_HASH"
        echo "\`\`\`"
        echo ""

        echo "**Diff:**"
        echo "\`\`\`diff"
        git show --format='' "$SHORT_HASH"
        echo "\`\`\`"
        echo ""
    done <<< "$COMMITS"
fi

# --- Current Project Tree ---
echo "## Current Project Tree"
echo ""
echo "\`\`\`"
find "$REPO_ROOT" \
    -path '*/.git' -prune -o \
    -path '*/logs' -prune -o \
    -path '*/node_modules' -prune -o \
    -name '.env' -prune -o \
    -name '*.pyc' -prune -o \
    -print | \
    sed "s|^${REPO_ROOT}/||" | \
    sed "s|^${REPO_ROOT}\$|.|" | \
    sort
echo "\`\`\`"
echo ""

# --- design.md Section Headers ---
echo "## design.md Section Headers"
echo ""

DESIGN_FILE="${REPO_ROOT}/design.md"
if [ -f "$DESIGN_FILE" ]; then
    LINE_NUM=0
    while IFS= read -r LINE; do
        LINE_NUM=$((LINE_NUM + 1))
        if [[ "$LINE" == \#* ]]; then
            echo "- ${LINE_NUM}: ${LINE}"
        fi
    done < "$DESIGN_FILE"
else
    echo "_design.md not found._"
fi
echo ""
