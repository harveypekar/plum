#!/bin/bash
# Persist the container's environment for cron jobs, which otherwise run
# with none of it (a classic cron-in-Docker gotcha: PID 1's env is not
# inherited by cron's spawned children).
set -euo pipefail

{
    printf 'export GARMIN_EMAIL=%q\n' "${GARMIN_EMAIL:-}"
    printf 'export GARMIN_PASSWORD=%q\n' "${GARMIN_PASSWORD:-}"
    printf 'export RCLONE_REMOTE=%q\n' "${RCLONE_REMOTE:-hetzner-crypt}"
    printf 'export GARMIN_DATA_DIR=%q\n' "${GARMIN_DATA_DIR:-/app/data/garmin}"
} > /etc/cron.env
chmod 600 /etc/cron.env

exec cron -f
