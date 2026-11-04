#!/bin/bash
# Uptime check for Healthchecks.io (TODO T5). Cron on each EC2, every 5 minutes:
#   */5 * * * * $HOME/monitor/check_up.sh <slug> <url>
# e.g. check_up.sh prod-api https://api.sariko.store/health
#
# Hits the PUBLIC url (DNS, nginx, TLS, app) and pings hc-ping.com/<key>/<slug>:
# success if it answered 2xx, /fail otherwise. A dead box sends nothing, so
# Healthchecks alerts once the grace time runs out. ?create=1 makes the check
# on its first ping; set its period/grace in the Healthchecks UI after that.
# ~/monitor/hc.env (chmod 600) holds HC_PING_KEY (Project settings → Ping key).
set -u
source "$HOME/monitor/hc.env"
SLUG=$1 URL=$2
PING="https://hc-ping.com/$HC_PING_KEY/$SLUG"

if curl -fsS -m 15 -o /dev/null "$URL"; then
  curl -fsS -m 10 --retry 3 -o /dev/null "$PING?create=1"
else
  curl -fsS -m 10 --retry 3 -o /dev/null "$PING/fail?create=1"
fi
