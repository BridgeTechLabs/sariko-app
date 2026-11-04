#!/usr/bin/env bash
# SQL tests of the money / portions / purge functions (docs/dev/test-sql), on the DEV database only.
# Each g*.sql makes its TEST rows inside one transaction and rolls back; the first failing file stops the run
# and psql prints its TC. Usage: tests/sql/run.sh <DEV database URL>
set -euo pipefail
url=${1:?usage: tests/sql/run.sh <DEV database URL>}
DEV_REF=saphxhqpjrhdsqbtnwqe  # as backend/supabase/scripts/push_to_dev.sh
[[ "$url" == *"$DEV_REF"* ]] || { echo "REFUSING: not the DEV database ($DEV_REF)." >&2; exit 1; }
echo "DEV project $DEV_REF"
cd "$(dirname "$0")"

test_rows() {
  psql "$url" -X -q -At -c "select (select count(*) from public.users where name like 'TEST sql%')
                                 + (select count(*) from public.seller_profiles where store_name like 'TEST sql%')
                                 + (select count(*) from public.orders where note like 'TEST sql%')"
}
before=$(test_rows)
for f in g*.sql; do
  echo "== $f"
  # the files' own begin / rollback inside --single-transaction warn about it; the rest of stderr is shown
  psql "$url" -X -q -v ON_ERROR_STOP=1 --single-transaction -f "$f" 2> >(grep -v 'transaction in progress' >&2) > /dev/null \
    || { echo "FAILED: $f" >&2; exit 1; }
done
after=$(test_rows)
[[ "$after" == "$before" ]] || { echo "TEST sql rows left: $before before, $after after" >&2; exit 1; }
echo "SQL tests passed"
