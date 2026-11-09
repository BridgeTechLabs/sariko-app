#!/bin/bash
# Test for infra/prod/backup/backup_db.sh (T166) without PROD, S3 or network:
# a throwaway local postgres:17 plays the DB (fake.now() = settable clock), stubs for docker / curl
# play pg_dump, S3 (folder s3/) and Storage (folder files/). Run: bash tests/infra/backup_db_test.sh
set -uo pipefail
SCRIPT="$(cd "$(dirname "$0")/../../infra/prod/backup" && pwd)/backup_db.sh"
W=$(mktemp -d)
PGC=backup-test-$$
REF=abcdefghijklmnopqrst
trap '/usr/bin/docker rm -f $PGC >/dev/null 2>&1; rm -rf "$W"' EXIT
mkdir -p "$W/home/backup" "$W/home/monitor" "$W/bin" "$W/pgbin" "$W/files" "$W/s3/daily"

/usr/bin/docker run -d --rm --name $PGC -e POSTGRES_USER=postgres.$REF -e POSTGRES_PASSWORD=pw -p 127.0.0.1::5432 postgres:17-alpine >/dev/null
PORT=$(/usr/bin/docker port $PGC 5432 | head -1 | sed 's/.*://')
DB="postgresql://postgres.$REF:pw@127.0.0.1:$PORT/postgres"
for _ in $(seq 30); do psql "$DB" -c 'select 1' >/dev/null 2>&1 && break; sleep 1; done
sql() { psql "$DB" -qAt -v ON_ERROR_STOP=1 -c "$1"; }
sql "create schema storage; create table storage.objects(bucket_id text, name text, created_at timestamptz, updated_at timestamptz);
     create schema fake; create table fake.clock(t timestamptz); insert into fake.clock values (null);
     create function fake.now() returns timestamptz language sql as 'select t from fake.clock';
     alter role current_user set search_path = fake, pg_catalog, public;"

cat > "$W/home/backup/.env.database" <<EOF
PROD_DB_URL=$DB
SUPABASE_SERVICE_KEY=fake-key
EOF
echo "HC_PING_KEY=fake" > "$W/home/monitor/hc.env"

# docker run ... postgres:17-alpine sh -c CMD  -> CMD here, /out = the mounted dir
# docker run ... amazon/aws-cli s3 cp /out/F s3://bucket/daily/K -> copy to s3/daily/K
cat > "$W/bin/docker" <<'EOF'
#!/bin/bash
echo "docker $*" >> "$W/calls"
shift; envs=()
while [[ $1 == -* ]]; do
  case $1 in -e) envs+=("$2"); shift 2;; -v) vol=${2%%:/out*}; shift 2;; --network) shift 2;; *) shift;; esac
done
img=$1; shift
case $img in
  postgres:*) env "${envs[@]}" PATH="$W/pgbin:$PATH" sh -c "${3//\/out/$vol}";;
  amazon/aws-cli:*) cp "$vol/${3#/out/}" "$W/s3/${4#s3://*/}";;
esac
EOF
cat > "$W/pgbin/pg_dump" <<'EOF'
#!/bin/bash
while [ $# -gt 0 ]; do [ "$1" = -f ] && echo dump > "$2"; shift; done
EOF
printf '#!/bin/sh\n' > "$W/pgbin/pg_restore"
# Storage: files/<bucket>/<name>; a path listed in $W/fail answers 500; no file = 400 NoSuchKey.
cat > "$W/bin/curl" <<'EOF'
#!/bin/bash
while [ $# -gt 0 ]; do case $1 in -o) out=$2; shift;; -w|-H|-m|--retry) shift;; -*) ;; *) url=$1;; esac; shift; done
echo "curl $url" >> "$W/calls"
[[ $url == https://hc-ping.com/* ]] && exit 0
[[ $url == *[\ \#]* ]] && { printf 000; exit 3; }   # unencoded space / # never reaches the server
p=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))' "${url#*/object/authenticated/}")
mkdir -p "$(dirname "$out")"
if grep -qxF "$p" "$W/fail" 2>/dev/null; then echo oops > "$out"; printf 500
elif [ -f "$W/files/$p" ]; then cp "$W/files/$p" "$out"; printf 200
else echo '{"statusCode":"404","error":"not_found","message":"Object not found","code":"NoSuchKey"}' > "$out"; printf 400; fi
EOF
chmod +x "$W/bin/"* "$W/pgbin/"*
export W

PASS=0; FAILS=0
ok() { if eval "$2"; then PASS=$((PASS + 1)); echo "ok   $1"; else FAILS=$((FAILS + 1)); echo "FAIL $1: $2"; fi; }
clock() { sql "update fake.clock set t = '$1'"; }
# obj <bucket/name> <content> <updated_at>: file in Storage + row in storage.objects
obj() {
  mkdir -p "$(dirname "$W/files/$1")"; printf %s "$2" > "$W/files/$1"
  sql "delete from storage.objects where bucket_id || '/' || name = \$q\$$1\$q\$;
       insert into storage.objects values (split_part(\$q\$$1\$q\$, '/', 1), substr(\$q\$$1\$q\$, strpos(\$q\$$1\$q\$, '/') + 1), '$3', '$3')"
}
# shellcheck disable=SC2034  # RC is read inside ok's eval
run() { : > "$W/calls"; HOME="$W/home" PATH="$W/bin:$PATH" bash "$SCRIPT" > "$W/out" 2>&1; RC=$?; }
last_tar() { ls -t "$W/s3/daily/"sariko_storage_* | head -1; }
kind() { basename "$(last_tar)" | cut -d_ -f3; }
tarlist() { tar -tf "$(last_tar)" | grep -v '/$' | sed 's#^\./##' | sort | tr '\n' ' '; }
st() { cat "$W/home/backup/state/$1" 2>/dev/null; }
reset() { rm -rf "$W/home/backup/state" "$W/s3/daily/"* "$W/files/"* "$W/fail"; sql "truncate storage.objects"; }

echo "TC-6 static"
ok "bash -n" "bash -n '$SCRIPT'"
if command -v shellcheck >/dev/null; then ok "shellcheck" "shellcheck -S warning '$SCRIPT'"; else echo "skip shellcheck (not installed)"; fi

echo "TC-1 no marks -> full, every object, both marks"
reset; clock '2026-11-10 19:15:00+00'   # Wednesday 02:15 VN
obj sariko-public/a.jpg A '2026-11-01 00:00+00'; obj complaints/b.jpg B '2026-11-02 00:00+00'
run
ok "exit 0" '[ $RC = 0 ]'
ok "full tar" '[ "$(kind)" = full ]'
ok "all objects" '[ "$(tarlist)" = "complaints/b.jpg sariko-public/a.jpg " ]'
ok "last_ok = DB now" '[ "$(st storage_last_ok)" = 2026-11-10T19:15:00.000000Z ]'
ok "last_full = DB now" '[ "$(st storage_last_full)" = 2026-11-10T19:15:00.000000Z ]'
ok "log line" 'grep -q "uploaded daily/sariko_storage_full_.*(2 objects, 0 failed, 0 missing, " "$W/out"'
ok "pings start + success" 'grep -q "prod-db-backup/start" "$W/calls" && grep -q "prod-db-backup?create" "$W/calls"'
ok "no tmp mark left" '! ls "$W/home/backup/state/"*.tmp 2>/dev/null'

echo "TC-2 / TC-5 / TC-12 inc: only changed objects, 10 min overlap"
obj sariko-public/new.jpg N '2026-11-10 19:15:01+00'    # TC-5: created right after last run's now()
obj sariko-public/late.jpg L '2026-11-10 19:14:55+00'   # TC-12: committed late, updated_at before the mark
clock '2026-11-11 19:15:00+00'   # Thursday VN
run
ok "exit 0" '[ $RC = 0 ]'
ok "inc tar" '[ "$(kind)" = inc ]'
ok "only new + late" '[ "$(tarlist)" = "sariko-public/late.jpg sariko-public/new.jpg " ]'
ok "last_ok moved" '[ "$(st storage_last_ok)" = 2026-11-11T19:15:00.000000Z ]'
ok "last_full kept" '[ "$(st storage_last_full)" = 2026-11-10T19:15:00.000000Z ]'

echo "TC-14 nothing changed -> empty valid tar, marks move"
clock '2026-11-11 20:15:00+00'
run
ok "inc tar readable, empty" '[ "$(kind)" = inc ] && tar -tf "$(last_tar)" >/dev/null && [ -z "$(tarlist)" ]'
ok "0 objects logged" 'grep -q "(0 objects, 0 failed, 0 missing" "$W/out"'
ok "last_ok moved" '[ "$(st storage_last_ok)" = 2026-11-11T20:15:00.000000Z ]'

echo "TC-4 a failed download keeps the marks and reports /fail; next night fetches it"
obj sariko-public/flaky.jpg F '2026-11-12 10:00+00'
echo sariko-public/flaky.jpg > "$W/fail"
clock '2026-11-12 19:15:00+00'   # Friday VN
run
ok "exit non-zero" '[ $RC != 0 ]'
ok "/fail ping" 'grep -q "prod-db-backup/fail" "$W/calls"'
ok "failed logged" 'grep -q "storage: failed sariko-public/flaky.jpg (HTTP 500)" "$W/out"'
ok "last_ok kept" '[ "$(st storage_last_ok)" = 2026-11-11T20:15:00.000000Z ]'
rm "$W/fail"; clock '2026-11-13 19:15:00+00'   # Saturday VN
run
ok "next night inc has it" '[ $RC = 0 ] && [ "$(kind)" = inc ] && [ "$(tarlist)" = "sariko-public/flaky.jpg " ]'

echo "TC-13 1 row without a file among ~100: missing, no /fail, marks move, no full every night"
mkdir -p "$W/files/sariko-public/bulk"; for i in $(seq 100); do echo "$i" > "$W/files/sariko-public/bulk/$i.jpg"; done
sql "insert into storage.objects select 'sariko-public', 'bulk/' || i || '.jpg', '2026-11-14 09:00+00', '2026-11-14 09:00+00' from generate_series(1, 100) i;
     insert into storage.objects values ('complaints', 'gone.jpg', '2026-11-14 10:00+00', '2026-11-14 10:00+00')"
clock '2026-11-14 19:15:00+00'   # Saturday 19:15 UTC = Sunday 02:15 VN -> full anyway
run
ok "exit 0" '[ $RC = 0 ]'
ok "no /fail" '! grep -q "/fail" "$W/calls"'
ok "missing logged by name" 'grep -q "storage: missing complaints/gone.jpg" "$W/out" && grep -q "1 missing" "$W/out"'
ok "missing not in tar" '! tarlist | grep -q gone.jpg'
ok "last_full moved" '[ "$(st storage_last_full)" = 2026-11-14T19:15:00.000000Z ]'
clock '2026-11-15 19:15:00+00'; run
ok "next night inc, missing gone from the list" '[ $RC = 0 ] && [ "$(kind)" = inc ] && grep -q "(0 objects" "$W/out"'

echo "TC-13b 50 rows without a file (Storage lost files) -> /fail, marks kept"
sql "insert into storage.objects select 'complaints', 'lost/' || i || '.jpg', '2026-11-16 10:00+00', '2026-11-16 10:00+00' from generate_series(1, 50) i"
clock '2026-11-16 19:15:00+00'; run   # Tuesday VN
ok "exit non-zero + /fail" '[ $RC != 0 ] && grep -q "prod-db-backup/fail" "$W/calls"'
ok "counted as failed" 'grep -q "50 of 50 files missing, counted as failed" "$W/out" && grep -q "50 failed, 50 missing" "$W/out"'
ok "marks kept" '[ "$(st storage_last_ok)" = 2026-11-15T19:15:00.000000Z ] && [ "$(st storage_last_full)" = 2026-11-14T19:15:00.000000Z ]'
sql "delete from storage.objects where name like 'lost/%'"

echo "TC-13c small inc: 3 objects, 1 without a file -> missing only, no /fail"
obj sariko-public/s1.jpg S1 '2026-11-17 10:00+00'; obj sariko-public/s2.jpg S2 '2026-11-17 10:00+00'
sql "insert into storage.objects values ('complaints', 'orphan.jpg', '2026-11-17 10:00+00', '2026-11-17 10:00+00')"
clock '2026-11-17 19:15:00+00'; run   # Wednesday VN
ok "exit 0, no /fail" '[ $RC = 0 ] && ! grep -q "/fail" "$W/calls"'
ok "inc, 3 objects, 1 missing" '[ "$(kind)" = inc ] && grep -q "(3 objects, 0 failed, 1 missing" "$W/out"'
ok "last_ok moved" '[ "$(st storage_last_ok)" = 2026-11-17T19:15:00.000000Z ]'

echo "TC-3 / TC-9 Sunday in VN from DB time, same result whatever TZ"
for tz in UTC Asia/Ho_Chi_Minh; do
  export TZ=$tz
  clock '2026-11-21 19:15:00+00'; run   # Saturday UTC = Sunday 02:15 VN
  ok "$tz: Sat 19:15 UTC -> full" '[ "$(kind)" = full ]'
  clock '2026-11-22 19:15:00+00'; run   # Sunday UTC = Monday 02:15 VN
  ok "$tz: Sun 19:15 UTC -> inc" '[ "$(kind)" = inc ]'
done
unset TZ
echo "2026-11-14T19:15:00.000000Z" > "$W/home/backup/state/storage_last_full"
clock '2026-11-24 19:15:00+00'; run   # Wednesday VN, last full 10 days ago
ok "last full > 7 days -> full" '[ "$(kind)" = full ]'

echo "TC-10 broken marks -> full, nothing odd reaches SQL"
for bad in "" "garbage" "2026-11-24'; drop table storage.objects; --"; do
  printf %s "$bad" > "$W/home/backup/state/storage_last_ok"
  clock '2026-11-25 19:15:00+00'; run
  ok "mark '${bad:0:12}' -> full" '[ $RC = 0 ] && [ "$(kind)" = full ]'
done
ok "table still there" '[ "$(sql "select count(*) > 0 from storage.objects")" = t ]'

echo "TC-15 names with space, Vietnamese, %, #"
reset; clock '2026-11-25 19:15:00+00'
obj "sariko-public/quán Bà Năm/món #1 50%.jpg" X '2026-11-25 10:00+00'
run
ok "fetched + right path in tar" '[ $RC = 0 ] && [ "$(tarlist)" = "sariko-public/quán Bà Năm/món #1 50%.jpg " ]'
mkdir "$W/x"; tar -xf "$(last_tar)" -C "$W/x"
ok "extracts with content" '[ "$(cat "$W/x/sariko-public/quán Bà Năm/món #1 50%.jpg")" = X ]'

echo "TC-11 DRY_RUN: no S3, no pings, no marks"
reset; clock '2026-11-25 19:15:00+00'; obj sariko-public/a.jpg A '2026-11-01 00:00+00'
DRY_RUN=1 run
ok "exit 0" '[ $RC = 0 ]'
ok "no aws, no hc" '! grep -q aws-cli "$W/calls" && ! grep -q hc-ping "$W/calls"'
ok "says what it would upload" 'grep -q "DRY_RUN: would upload daily/sariko_storage_full_" "$W/out"'
ok "no marks, no S3 file" '[ -z "$(st storage_last_ok)$(st storage_last_full)" ] && [ -z "$(ls "$W/s3/daily")" ]'
ok "only stubbed network" '! grep "^curl " "$W/calls" | grep -v "^curl https://$REF.supabase.co/"'

echo "flock: second run while one holds the lock exits 0"
mkdir -p "$W/home/backup/state"; exec 8>"$W/home/backup/state/.lock"; flock 8
run
ok "already running, exit 0, nothing uploaded" '[ $RC = 0 ] && grep -q "already running" "$W/out" && [ ! -s "$W/calls" ]'
exec 8>&-

echo "TC-18 restore order: full A, inc B, inc C, full D of one path; restore command from the script header -> D"
reset
obj sariko-public/p.jpg A '2026-11-10 10:00+00'; clock '2026-11-10 19:15:00+00'; run; sleep 1
obj sariko-public/p.jpg B '2026-11-11 10:00+00'; clock '2026-11-11 19:15:00+00'; run; sleep 1
obj sariko-public/p.jpg C '2026-11-12 10:00+00'; clock '2026-11-12 19:15:00+00'; run; sleep 1
obj sariko-public/p.jpg D '2026-11-14 10:00+00'; clock '2026-11-14 19:15:00+00'; run   # Sunday VN -> full
ok "2 full + 2 inc" '[ "$(ls "$W/s3/daily/" | grep -c storage_full_)" = 2 ] && [ "$(ls "$W/s3/daily/" | grep -c storage_inc_)" = 2 ]'
restore=$(grep -o 'for f in .*done' "$SCRIPT")
(cd "$W/s3/daily" && mkdir restored && eval "$restore")
ok "restored file is D" '[ "$(cat "$W/s3/daily/restored/sariko-public/p.jpg")" = D ]'

echo "passed $PASS, failed $FAILS"
[ $FAILS = 0 ]
