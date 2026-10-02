#!/usr/bin/env bash
set -euo pipefail

# supabase CLI tìm supabase/config.toml theo cwd
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
 
PROD_REF=wrqazccevjgrhhxfmjoi
ref=${1:-saphxhqpjrhdsqbtnwqe}

# The only guard worth keeping: this command destroys whatever it points at.
[[ "$ref" != "$PROD_REF" ]] || { echo "REFUSING: that is the production project." >&2; exit 1; }

echo "Resetting project $ref — all its data will be dropped."
read -rp "Continue? [y/N] " reply
[[ "$reply" == [yY] ]] || exit 1

supabase login

# Leave no ambient link behind: whichever project stays linked is what a bare
# `supabase db reset --linked` would destroy later.
trap 'supabase unlink >/dev/null 2>&1 || true' EXIT
supabase link --project-ref "$ref"
supabase db reset --linked

# The reset dropped the whole database, including objects this repo does not own:
# the admin_* payout functions live in the admin repo.
echo
echo "NOTE: admin_* functions are owned by the admin repo — re-apply its migrations."
