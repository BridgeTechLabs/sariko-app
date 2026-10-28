#!/bin/bash
# Disk check for Healthchecks.io. Cron on each EC2, every hour:
#   0 * * * * $HOME/monitor/check_disk.sh <slug>
# e.g. check_disk.sh dev-disk
#
# Pings hc-ping.com/<key>/<slug> with "Disk N% used" as the body (a webhook shows it via $BODY): success below
# LIMIT % used on /, /fail at or above it. GitHub runners leave the old version
# behind on each self-update (_work/_update, bin.*, externals.*), so the disk
# fills slowly. The default period (1 day) is enough: /fail alerts at once.
# ~/monitor/hc.env (chmod 600) holds HC_PING_KEY (Project settings → Ping key).
set -u
source "$HOME/monitor/hc.env"
SLUG=$1 LIMIT=${2:-85}
PCT=$(df --output=pcent / | tail -1 | tr -dc 0-9)
PING="https://hc-ping.com/$HC_PING_KEY/$SLUG"

if [ "$PCT" -lt "$LIMIT" ]; then
  curl -fsS -m 10 --retry 3 -o /dev/null --data-raw "Disk $PCT% used" "$PING?create=1"
else
  curl -fsS -m 10 --retry 3 -o /dev/null --data-raw "Disk almost full: $PCT% used (alert at $LIMIT%)" "$PING/fail?create=1"
fi
