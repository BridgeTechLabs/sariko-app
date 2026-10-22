#!/bin/bash
# Nightly dump of the PROD Supabase database + Storage files to S3 (TODO T1). Runs from cron on
# the PROD EC2 as ~/backup/backup_db.sh:
#   15 19 * * * $HOME/backup/backup_db.sh >> $HOME/backup/backup.log 2>&1   (02:15 VN)
#
# - ~/backup/.env.database (chmod 600) holds PROD_DB_URL = the Session pooler URI
#   (port 5432; the direct host is IPv6-only).
# - pg_dump and aws run in containers: nothing to install on the server.
# - The instance role (sariko-prod-ec2) may only PutObject under daily/, so this
#   box can neither read nor delete backups. The bucket's lifecycle rule
#   expire-daily-7d deletes them after 7 days.
# - Storage files (images): every object listed in storage.objects is fetched
#   from its public URL (all buckets are public, so no extra key) and uploaded
#   as one tar next to the dump. A file that fails to download is logged and
#   skipped; the run still uploads the rest, then reports /fail.
# - Healthchecks.io check `prod-db-backup` (TODO T5): /start, then success or
#   /fail. Key in ~/monitor/hc.env; no key file = no pings, backup still runs.
set -euo pipefail

BUCKET=sariko-prod-db-backups
PG_IMAGE=postgres:17-alpine          # match the server's major version (17)
AWS_IMAGE=amazon/aws-cli:2.27.0

source "$HOME/backup/.env.database"
: "${PROD_DB_URL:?PROD_DB_URL missing in ~/backup/.env.database}"

[ -f "$HOME/monitor/hc.env" ] && source "$HOME/monitor/hc.env"
hc() {  # a failed ping must never fail the backup
  [ -n "${HC_PING_KEY:-}" ] || return 0
  curl -fsS -m 10 --retry 3 -o /dev/null "https://hc-ping.com/$HC_PING_KEY/prod-db-backup$1?create=1" || true
}
trap 'hc /fail' ERR
hc /start

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "[$STAMP] dump start"

# Custom format (compressed, restorable table by table). auth holds the login
# accounts public.users points at; storage holds the file metadata.
docker run --rm -e PGURL="$PROD_DB_URL" -v "$TMP:/out" "$PG_IMAGE" sh -c '
  pg_dump "$PGURL" -Fc --no-owner --no-privileges -n public -n auth -n storage -f /out/db.dump &&
  pg_restore --list /out/db.dump > /dev/null &&   # a dump that cannot be listed is not uploaded
  psql "$PGURL" -At -c "select bucket_id || '\''/'\'' || name from storage.objects order by 1" > /out/objects.txt'

SIZE=$(stat -c %s "$TMP/db.dump")
# --network host: containers on the bridge can't reach the instance metadata
# service when the IMDSv2 hop limit is 1, so the role credentials wouldn't load.
docker run --rm --network host -e AWS_DEFAULT_REGION=ap-northeast-2 -v "$TMP:/out:ro" "$AWS_IMAGE" \
  s3 cp /out/db.dump "s3://$BUCKET/daily/sariko_prod_$STAMP.dump" --only-show-errors

echo "[$STAMP] uploaded daily/sariko_prod_$STAMP.dump ($SIZE bytes)"

# Project ref = the pooler user name "postgres.<ref>".
REF=$(sed -E 's#^[a-z]+://postgres\.([a-z0-9]+):.*#\1#' <<<"$PROD_DB_URL")
[[ $REF =~ ^[a-z0-9]{20}$ ]] || { echo "cannot read project ref from PROD_DB_URL"; false; }
BASE="https://$REF.supabase.co/storage/v1/object/public"

FAILED=0
mkdir "$TMP/storage"
while IFS= read -r path; do
  url="$BASE/$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$path")"
  curl -fsS -m 60 --retry 2 --create-dirs -o "$TMP/storage/$path" "$url" \
    || { echo "[$STAMP] storage: failed $path"; FAILED=$((FAILED + 1)); }
done < "$TMP/objects.txt"

tar -C "$TMP/storage" -cf "$TMP/storage.tar" .
docker run --rm --network host -e AWS_DEFAULT_REGION=ap-northeast-2 -v "$TMP:/out:ro" "$AWS_IMAGE" \
  s3 cp /out/storage.tar "s3://$BUCKET/daily/sariko_storage_$STAMP.tar" --only-show-errors

echo "[$STAMP] uploaded daily/sariko_storage_$STAMP.tar ($(wc -l < "$TMP/objects.txt") objects, $FAILED failed, $(stat -c %s "$TMP/storage.tar") bytes)"
[ "$FAILED" -eq 0 ] || false   # ERR trap pings /fail
hc ""
