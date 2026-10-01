#!/usr/bin/env bash
set -euo pipefail

# Put dish photos behind the mock food_items in seeds/03_mock_data.sql.
# Run after push_to_dev.sh: a db reset leaves the bucket empty.
#
# Source is prod's PUBLIC bucket (plain GET, no prod key). Only dish photos —
# never avatar-buyers / avatar-sellers, those are real people.

cd "$(dirname "${BASH_SOURCE[0]}")/../../src"
set -a; . envs/.env.dev; set +a

PROD_REF=wrqazccevjgrhhxfmjoi
[[ "$SUPABASE_URL" != *"$PROD_REF"* ]] || { echo "REFUSING: .env.dev points at production." >&2; exit 1; }

SRC=https://$PROD_REF.supabase.co/storage/v1/object/public/sariko-public/food-items/86b1d707-447b-47a7-838b-2e947bbd6b84
SELLER_ROSA=aaaaaaaa-0000-0000-0000-000000000001
SELLER_BEN=aaaaaaaa-0000-0000-0000-000000000002

# dev path (food-items/{seller_id}/{item_id})          prod file
while read -r dst src; do
  curl -sSf "$SRC/$src" | curl -sSf -o /dev/null -X POST \
    -H "apikey: $SUPABASE_API_KEY" -H "Authorization: Bearer $SUPABASE_API_KEY" \
    -H "x-upsert: true" -H "Content-Type: image/jpeg" \
    --data-binary @- "$SUPABASE_URL/storage/v1/object/sariko-public/food-items/$dst"
  echo "ok  $dst"
done <<EOF
$SELLER_ROSA/cccccccc-0000-0000-0000-000000000001 4d6b439b-0f62-4d96-8eef-812f0cfe3e7e.jpg
$SELLER_ROSA/cccccccc-0000-0000-0000-000000000002 8d766786-d5b1-4055-abe0-e7b29655c003.jpg
$SELLER_ROSA/cccccccc-0000-0000-0000-000000000003 1ee2cdcf-a7e9-445e-8ae0-08fd55c2e056.jpg
$SELLER_ROSA/cccccccc-0000-0000-0000-000000000004 5abd590a-5d33-4d16-b822-c938b5ea9549.jpg
$SELLER_BEN/cccccccc-0000-0000-0000-000000000005  024258d2-a961-4574-9464-7fabb45ec7c7.jpg
EOF
