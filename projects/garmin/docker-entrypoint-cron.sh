#!/bin/bash
# Persist the container's environment for cron jobs, which otherwise run
# with none of it (a classic cron-in-Docker gotcha: PID 1's env is not
# inherited by cron's spawned children).
set -euo pipefail

{
    echo "export GARMIN_EMAIL='${GARMIN_EMAIL:-}'"
    echo "export GARMIN_PASSWORD='${GARMIN_PASSWORD:-}'"
    echo "export RCLONE_REMOTE='${RCLONE_REMOTE:-hetzner-crypt}'"
    echo "export GARMIN_DATA_DIR='${GARMIN_DATA_DIR:-/app/data/garmin}'"
} > /etc/cron.env
chmod 600 /etc/cron.env

exec cron -f
