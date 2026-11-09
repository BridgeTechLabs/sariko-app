#!/bin/bash
# Nightly dump of the PROD Supabase database + Storage files to S3 (TODO T1). Runs from cron on
# the PROD EC2 as ~/backup/backup_db.sh:
#   15 19 * * * $HOME/backup/backup_db.sh >> $HOME/backup/backup.log 2>&1   (02:15 VN)
#
# - ~/backup/.env.database (chmod 600) holds PROD_DB_URL = the Session pooler URI
#   (port 5432; the direct host is IPv6-only) and SUPABASE_SERVICE_KEY (service role key).
# - pg_dump and aws run in containers: nothing to install on the server.
# - The instance role (sariko-prod-ec2) may only PutObject under daily/, so this
#   box can neither read nor delete backups. The bucket's lifecycle rule
#   expire-daily-7d deletes them after 15 days (T166; it was 7).
# - Storage files (images), fetched with the service role key (two buckets are private),
#   uploaded as one tar next to the dump (T166):
#     sariko_storage_full_<STAMP>.tar  every object: on Sunday (VN), when there is no mark,
#                                      or when the last full is older than 7 days
#     sariko_storage_inc_<STAMP>.tar   objects created or changed since the previous good run
#                                      (10 minutes of overlap); can be empty
#   Marks are DB times in ~/backup/state/storage_last_ok and storage_last_full, written only
#   after the upload with 0 failed files. A failed file keeps the marks (next night fetches it
#   again) and reports /fail. A file Storage says does not exist is logged as missing: no /fail,
#   unless more than 20, or more than 3 and over 10%, of the listed files are missing (Storage lost
#   files): then failed.
#   Deletions are not recorded, so a restore can bring back deleted files (harmless: storage.objects
#   in the dump is the true list). With 15-day expiry a restore point is guaranteed ~9 days back.
# - Restore Storage to time T (needs an account that can read the bucket):
#   1. download the newest sariko_storage_full_<STAMP>.tar with STAMP <= T
#   2. download every sariko_storage_inc_<STAMP>.tar newer than that full and <= T, same folder
#   3. extract in STAMP order (field 4 of the name; newer overwrites older):
#      for f in $(ls sariko_storage_*.tar | sort -t_ -k4); do tar -xf "$f" -C restored/; done
# - DRY_RUN=1: no S3 upload, no pings, no marks (still dumps and downloads: not a PROD test).
# - Healthchecks.io check `prod-db-backup` (TODO T5): /start, then success or
#   /fail. Key in ~/monitor/hc.env; no key file = no pings, backup still runs.
set -euo pipefail

BUCKET=sariko-prod-db-backups
PG_IMAGE=postgres:17-alpine          # match the server's major version (17)
AWS_IMAGE=amazon/aws-cli:2.27.0
STATE="$HOME/backup/state"

mkdir -p "$STATE"
exec 9>"$STATE/.lock"
flock -n 9 || { echo "already running"; exit 0; }

source "$HOME/backup/.env.database"
: "${PROD_DB_URL:?PROD_DB_URL missing in ~/backup/.env.database}"

[ -f "$HOME/monitor/hc.env" ] && source "$HOME/monitor/hc.env"
hc() {  # a failed ping must never fail the backup
  [ -n "${HC_PING_KEY:-}" ] && [ -z "${DRY_RUN:-}" ] || return 0
  curl -fsS -m 10 --retry 3 -o /dev/null "https://hc-ping.com/$HC_PING_KEY/prod-db-backup$1?create=1" || true
}
trap 'hc /fail' ERR
hc /start

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

s3put() {  # $1 = file in $TMP, $2 = name under daily/
  if [ -n "${DRY_RUN:-}" ]; then echo "[$STAMP] DRY_RUN: would upload daily/$2"; return; fi
  # --network host: containers on the bridge can't reach the instance metadata
  # service when the IMDSv2 hop limit is 1, so the role credentials wouldn't load.
  docker run --rm --network host -e AWS_DEFAULT_REGION=ap-northeast-2 -v "$TMP:/out:ro" "$AWS_IMAGE" \
    s3 cp "/out/$1" "s3://$BUCKET/daily/$2" --only-show-errors
}

mark() {  # a mark that is not a time we wrote counts as none (= full run)
  local v
  v=$(cat "$STATE/$1" 2>/dev/null) || true
  [[ $v =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$ ]] && echo "$v" || true
}

# First line: run kind + DB now(); then the objects to fetch. One statement, so the time, the
# weekday and the list come from the same moment, none from this box's clock (UTC).
cat > "$TMP/list.sql" <<'SQL'
with t as (
  select now() as n,
    extract(isodow from now() at time zone 'Asia/Ho_Chi_Minh') = 7
    or nullif(:'last_ok', '') is null
    or coalesce(nullif(:'last_full', '')::timestamptz < now() - interval '7 days', true) as is_full
)
select line from (
  select 0 as k, case when is_full then 'full' else 'inc' end || ' '
    || to_char(n at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') as line from t
  union all
  select 1, o.bucket_id || '/' || o.name from storage.objects o, t
  where is_full or coalesce(o.updated_at, o.created_at) > nullif(:'last_ok', '')::timestamptz - interval '10 minutes'
) x order by k, line;
SQL

echo "[$STAMP] dump start"

# Custom format (compressed, restorable table by table). auth holds the login
# accounts public.users points at; storage holds the file metadata.
docker run --rm -e PGURL="$PROD_DB_URL" -e LAST_OK="$(mark storage_last_ok)" -e LAST_FULL="$(mark storage_last_full)" \
  -v "$TMP:/out" "$PG_IMAGE" sh -c '
  pg_dump "$PGURL" -Fc --no-owner --no-privileges -n public -n auth -n storage -f /out/db.dump &&
  pg_restore --list /out/db.dump > /dev/null &&   # a dump that cannot be listed is not uploaded
  psql "$PGURL" -At -v ON_ERROR_STOP=1 -v last_ok="$LAST_OK" -v last_full="$LAST_FULL" -f /out/list.sql > /out/list.txt'

SIZE=$(stat -c %s "$TMP/db.dump")
s3put db.dump "sariko_prod_$STAMP.dump"
echo "[$STAMP] uploaded daily/sariko_prod_$STAMP.dump ($SIZE bytes)"

read -r MODE NOW < "$TMP/list.txt"
tail -n +2 "$TMP/list.txt" > "$TMP/objects.txt"

# Project ref = the pooler user name "postgres.<ref>".
REF=$(sed -E 's#^[a-z]+://postgres\.([a-z0-9]+):.*#\1#' <<<"$PROD_DB_URL")
[[ $REF =~ ^[a-z0-9]{20}$ ]] || { echo "cannot read project ref from PROD_DB_URL"; false; }
# Private buckets (onboarding-files, complaints) need the service role key; it reads public ones too.
: "${SUPABASE_SERVICE_KEY:?SUPABASE_SERVICE_KEY missing in ~/backup/.env.database}"
BASE="https://$REF.supabase.co/storage/v1/object/authenticated"

FAILED=0
MISSING=0
mkdir "$TMP/storage"
while IFS= read -r path; do
  out="$TMP/storage/$path"
  url="$BASE/$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$path")"
  code=$(curl -sS -m 60 --retry 2 --create-dirs -o "$out" -w '%{http_code}' -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" "$url") || true
  [ "$code" = 200 ] && continue
  # Storage answers 400 with code NoSuchKey when the row exists but the file does not.
  if [ "$code" = 404 ] || grep -qs NoSuchKey "$out"; then
    echo "[$STAMP] storage: missing $path"; MISSING=$((MISSING + 1))
  else
    echo "[$STAMP] storage: failed $path (HTTP $code)"; FAILED=$((FAILED + 1))
  fi
  rm -f "$out"
done < "$TMP/objects.txt"
TOTAL=$(wc -l < "$TMP/objects.txt")
if [ "$MISSING" -gt 20 ] || { [ "$MISSING" -gt 3 ] && [ $((MISSING * 10)) -gt "$TOTAL" ]; }; then
  echo "[$STAMP] storage: $MISSING of $TOTAL files missing, counted as failed"; FAILED=$((FAILED + MISSING))
fi

NAME="sariko_storage_${MODE}_$STAMP.tar"
tar -C "$TMP/storage" -cf "$TMP/storage.tar" .
s3put storage.tar "$NAME"
echo "[$STAMP] uploaded daily/$NAME ($TOTAL objects, $FAILED failed, $MISSING missing, $(stat -c %s "$TMP/storage.tar") bytes)"
[ "$FAILED" -eq 0 ] || false   # ERR trap pings /fail; marks stay so the next run fetches them again

save() { echo "$NOW" > "$STATE/$1.tmp"; mv "$STATE/$1.tmp" "$STATE/$1"; }
if [ -z "${DRY_RUN:-}" ]; then
  [ "$MODE" = inc ] || save storage_last_full
  save storage_last_ok
fi
hc ""
