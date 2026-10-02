#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=wrqazccevjgrhhxfmjoi
SUPABASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFERENCE_DIR="$SUPABASE_DIR/reference"
# pattern: prod_data_<project-ref>_<YYYYMMDD-HHMMSS>.sql
OUT="$REFERENCE_DIR/prod_data_${PROJECT_ID}_$(date +%Y%m%d-%H%M%S).sql"

supabase login

# Unlink on the way out, however we leave — a lingering link to prod is one
# `supabase db reset --linked` away from wiping it.
trap 'supabase unlink >/dev/null 2>&1 || true' EXIT
supabase link --project-ref "$PROJECT_ID"

mkdir -p "$REFERENCE_DIR"
supabase db dump --linked --data-only \
  -x public.admin_tier_config \
  -x public.admin_tax_config \
  -x public.blog_posts \
  -x public.waitlist \
  -f "$OUT"

echo "Wrote $OUT"
echo "Reference only — db reset loads seeds/03_mock_data.sql, not this file."
echo "Unlinked from prod."
