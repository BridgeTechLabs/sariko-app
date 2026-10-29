# CLAUDE.md

Sariko: marketplace for home-cooked Filipino food in Ho Chi Minh City.
Vue 3 PWA (`frontend/`) + FastAPI (`backend/`) + Supabase (Postgres, Auth, Storage).
The admin app (payouts, refunds, operator UI) is a separate repo; it reaches this
backend only through the Admin Gateway endpoints (`X-Api-Key`).

## Working style
- Think first: state assumptions, ask when something is unclear, name tradeoffs.
- Write the minimum code that solves the task. No speculative features, abstractions or config.
- Keep diffs surgical: touch only what the task needs, match the surrounding style,
  remove only the orphans your change created.
- Every change has a check (test, script, screenshot) that you run before handing it over.

## Setup after clone
1. Frontend: `cd frontend && npm install && cp .env.example .env.development`, then fill the `VITE_*` values.
2. Backend (Python 3.11, same as the Docker image): `pip install -r backend/requirements.txt`,
   `cp backend/src/envs/.env.example backend/src/envs/.env.local`, then fill it.
   The backend loads `envs/.env.$ENV` (`ENV` defaults to `local`). `SUPABASE_JWKS_URL` is per
   Supabase project: a value from another project makes every request 401.
3. Database: there is no local Postgres. The schema is `backend/supabase/migrations/` (Supabase CLI).
   A fresh dev project: `backend/supabase/scripts/push_to_dev.sh <dev-project-ref>`
   (`db reset --linked` + seeds `00`, `01`, `03`; it refuses the prod ref). After a reset, re-apply
   the admin repo's `admin_*` functions. `backend/src/sql/` is legacy: don't edit it.
4. Run: `cd frontend && npm run dev` (http://localhost:8081, proxies `/rest` to :5000) and
   `cd backend/src && python main.py` (:5000, API docs at `/docs`).
   Dev panel `Ctrl+Shift+Q` (force-pay / force-status) needs `VITE_DEV_PANEL=true`; local and DEV only.
5. Checks: `pytest tests/backend -v` (CI runs it inside the image) and `cd frontend && npm run build`
   (runs the i18n compile check first).
6. Server files: `infra/<env>/` is copied to the EC2 home with `infra/sync.sh <env>` (dry run by
   default, `--apply` writes). It is not part of the deploy pipeline.

## Branches, CI, release
- Work on a feature branch (currently `feature-moit`) -> PR into `develop` -> DEV pipeline
  (pytest in the image, `supabase db push`, deploy, readiness check with rollback).
  `develop` -> `main` runs the same pipeline for PROD. PROD uses live VNPay + Lalamove: a merge to
  `main` handles real money.
- Commit messages in English with `feat:` / `fix:` / `refactor:`. When the maintainer gives a
  message, use it verbatim, with no added trailers.
- Never `git add .` or `commit -a`: untracked files hold secrets. Stage explicit paths.
- `docs/`, `.claude/`, `.config/` are gitignored and the repo is public: never commit them or `add -f`.

## Architecture
- Frontend: Vue 3 Options API, Quasar, Pinia, vue-router, lucide-vue-next icons.
  Page = Layout + Components: the layout owns slots and CSS; components own logic and read/write
  Pinia stores directly (no prop/event chains). HTTP goes through `frontend/src/apis/*`, and only
  stores import `apis/`: components call store actions, never `apis/` directly.
  `axiosPolicy.js` attaches the Supabase token.
- Backend: route handler -> DAO (`backend/src/dao/`) -> Supabase PostgREST. No DB calls in handlers,
  no ORM. Protected routes use `Depends(verify_token)` (JWKS). Every endpoint is under `/rest/v1/`.
- Image uploads go through backend endpoints with the service role, not client-side Storage
  (`auth.uid()` is NULL in storage-api with this project's ES256 JWTs).
- Live updates use `composables/createPoller.js` (10-15 s, stops on terminal states), not Realtime.
- UI: section-level `q-skeleton animation="pulse"`; VND shown as
  `new Intl.NumberFormat('vi-VN').format(amount) + ' ₫'`. Text for operators and sellers: plain
  speech, no variable / column names or codes, readable units (24 hours, not 1440 minutes), no
  person names (use roles).

## Hard rules
- Money: Python `Decimal(str(x))`, never `float`; JS keeps whole-VND integers, no `parseFloat`
  on money. Convert to int only at the boundary (VNPay: `int(Decimal(str(x)) * 100)`).
  `tests/backend/unit/test_no_float_money.py` enforces a shrinking baseline.
- Business parameters (fees, limits, time windows, percentages, counts, versions) live in
  `admin_settings` (per plan: `admin_tier_config`), read with
  `DAOAdminConfig.get_positive_int(key, default)`. Values are positive integers (percent as int,
  versions as YYYYMMDD). A new key = migration insert `on conflict (key) do nothing` with an English
  description. The frontend gets limits from an API, never from constants. Not parameters:
  protocol constants, enums, legal text, input-format checks.
- Migrations: new file `backend/supabase/migrations/<YYYYMMDDHHMMSS>_<name>.sql`, version unique
  across branches. Once a migration is on `develop` (`git branch -r --contains <commit>`), never edit
  or delete it: write a new one. New tables get a purpose prefix (`history_*` audit, `admin_*` admin,
  `metrics_*` monitoring rows deleted after N days). A migration that changes indexes, constraints or
  functions of an existing table: read `pg_indexes` / `pg_constraint` (/ `pg_proc`) on PROD and DEV
  first; PROD has objects made by hand that DEV lacks.
- i18n (`frontend/src/i18n/locales/{en-PH,vi}.json`): a raw `@`, `{`, `}` or `|` breaks vue-i18n at
  runtime; write `{'@'}`, `{'{'}`, `{'}'}`, `{'|'}`. `npm run check:i18n` compiles every message.
- V2 frontend belongs to another developer. Don't edit `frontend/src/**/v2/**`, `utils/theme.js`,
  `stores/theme/`, `plugins/theme.js`, `assets/main.css`, `assets/tokens.css`. Fix V1 in V1 files;
  V1 colours are in `assets/v1-legacy.css`.
- PROD is read-only except through the deploy pipeline and the maintainer. DEV test data is marked
  `TEST <flow>` and cleaned up afterwards. SQL check files start with `begin;` and run with
  `psql -v ON_ERROR_STOP=1 --single-transaction`.
- Changes to payments, refunds, payouts, auth, migrations or data deletion need automated tests and
  a line-by-line review.

## Tooling on this machine
- `rtk` filters command output, even when redirected to a file. For exact output use
  `rtk proxy <cmd>` (patches: `rtk proxy git diff -- <files> > x.diff`, then `git apply --check`).
  Edit files with the editor tools or Python, not `head`/`cat`/`sed` redirects.
- Multi-session workflow, specs and status live outside this repo, in a private workflow repo
  (start at its `sariko-app/CAU-HINH.txt`). A path written as `docs/...` in old notes or code
  comments points into that repo, not this one.
