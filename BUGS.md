# Bug Notes

Bugs found during manual testing. Newest at the bottom.

- **Status:** ⬜ Open · 🔧 Fixed in branch (not deployed) · ✅ Verified on DEV
- **Deployed:** which env runs the fix (`—` = nowhere yet), plus branch / commit

| # | Bug | Status | Deployed |
|---|-----|--------|----------|
| 1 | Buyer address toast on login (DEV missing migration) | 🔧 Fix in `fix/common-bugs`: pipeline runs `supabase db push` | — (applies on next `develop` deploy) |
| 2 | Seed `'vi'` ≠ `'Tiếng Việt'` → English pushes | ⬜ Open | — |
| 3 | VNPay "Sai chữ ký" (`vnp_IpnUrl`) | ⬜ Open | — |
| 4 | Push enable fails silently (Brave) | ⬜ Open | — |
| 5 | DEV pushes 403: VAPID key pair mismatch | 🔧 Keys rotated + backend redeployed; phone must re-subscribe | DEV backend `e6aac52` |
| 6 | Lalamove can't register webhook ("Destination host unreachable") | ✅ Verified on DEV: webhook `COMPLETED` → order `21939402` done (20:18 UTC) | DEV backend `29be3bd` |

---

## #1 — Buyer with no address gets an error toast on login
- **Found:** 2026-10-12, testing push on https://app-dev.sariko.store (DEV DB)
- **Steps:** Log in as a buyer with no saved address
- **Actual:** Red error toast while loading the address
- **Expected:** No toast. An empty address is not an error, since the buyer can add one later (checkout already blocks if the address is missing)
- **Where:**
  - Frontend calls `GET /v1/users/me/address` from `frontend/src/stores/auth/authStore.js` (bootstrap ~L154, signin ~L306)
  - The toast comes from the global axios interceptor `frontend/src/lib/axiosPolicy.js` (~L136). It fires on an error response even though authStore catches the error
  - Backend: `backend/src/apis/users.py` `get_default_address` → `DAOUserAddresses.read_default_address` (`.maybe_single()`)
- **Cause (confirmed 2026-10-12 on DEV): schema drift, not an empty address.**
  - DEV DB is missing migration `backend/supabase/migrations/20261003015158_add_new_columns_to_user_addresses.sql`: columns `receiver_name`, `phone_number`, `street_name`, `note` do not exist (PostgREST 42703). The later `20261009090000_create_push_subscriptions.sql` *is* applied, so the older one was skipped.
  - `read_default_address` selects those columns → query fails → **HTTP 500**. `GET /v1/user_addresses` (v2 Saved Addresses) fails the same way.
  - `.maybe_single()` hides the real error: the backend log shows `'Missing response', code '204'` instead of "column does not exist". This makes the bug look like "no address".
- **Fix:** Apply the missing migration to DEV (`supabase db push --include-all` against the dev project). No code change needed for this cause.
- **Follow-up (separate, still worth fixing):** If a buyer really has no default address, does `.maybe_single()` also raise 204 → 500 → toast? Re-test after the migration with a buyer who has no address. If yes, the endpoint should return `{address: null}` with 200.

---

## #2 — Push notifications ignore Vietnamese for seed users
- **Found:** 2026-10-12, code read during push test
- **Actual:** `backend/src/services/push_service.py` L99 only treats `preferred_language == "Tiếng Việt"` as Vietnamese. Mock seed (`backend/supabase/seeds/03_mock_data.sql`) stores `'vi'`, so seeded VI users get English pushes
- **Impact:** DEV only. Real users store `'Tiếng Việt'` via the app
- **Workaround:** Re-select Tiếng Việt in Account → Language before testing
- **Fix options:** Make the seed use `'Tiếng Việt'`, or have push_service also accept `'vi'`

---

## #3 — VNPay shows "Sai chữ ký" (code 70) on DEV checkout
- **Found:** 2026-10-12, paying an order on https://app-dev.sariko.store
- **Actual:** Redirect to VNPay sandbox lands on `Payment/Error.html?code=70`, which shows "Sai chữ ký" (invalid signature)
- **Expected:** VNPay payment method page
- **Cause (confirmed by reproduction against VNPay sandbox):** `backend/src/apis/payments.py` L101-102 adds `vnp_IpnUrl` to the signed params when `VNPAY_IPN_URL` is set. `vnp_IpnUrl` is not a VNPay 2.1.0 `pay` parameter, so VNPay leaves it out when it recomputes the hash, and the hashes no longer match.
  - Same TMN code + secret + params: **without** `vnp_IpnUrl` → PaymentMethod page OK; **with** it → code 70.
  - Only DEV sets `VNPAY_IPN_URL` (`infra/deploy-dev/.env.dev` L12). `.env.local` doesn't, so local never hit it.
- **Fix options:**
  - Code (recommended): delete the `if VNPAY_IPN_URL` block and the `VNPAY_IPN_URL` env var (not used anywhere else). The IPN URL is registered on the VNPay merchant portal, not sent per request.
  - Workaround with no deploy: remove `VNPAY_IPN_URL` from the env file on the dev EC2 (`~/deploy`), then `docker compose up -d`.
- **Watch out:** Don't set `VNPAY_IPN_URL` on prod either, or prod checkout breaks the same way.

---

## #4 — Enabling push fails silently (e.g. on Brave)
- **Found:** 2026-10-12, enabling push notifications on app-dev with Brave
- **Actual:** The toggle flips back to Off with no message. No row is written to `push_subscriptions`
- **Expected:** A toast explaining that push couldn't be enabled on this browser
- **Cause (very likely, not yet confirmed in console):** Brave disables Web Push by default (Chromium push goes through Google FCM). `pushManager.subscribe()` throws, and `togglePush` in `frontend/src/stores/v2/account/accountStore.js` (~L243-262) only `console.warn`s inside `catch`. Only the `unsupported`/`blocked` results show a toast.
- **Fix idea:** In the `catch`, show the same negative Notify (e.g. reuse `account_v2.push_unsupported` or add a "couldn't enable, check browser settings" message).
- **Workaround for testing on Brave:** `brave://settings/privacy` → enable "Use Google services for push messaging" → restart Brave.

---

## #5 — No push arrives on DEV: VAPID key pair mismatch (403)
- **Found:** 2026-10-12. `seller@dev.local` subscribed on Android Chrome (3 rows in `push_subscriptions`); force-pay on order `21939402` at 19:43 UTC → no notification
- **Evidence (dev EC2 backend log):** `push_service - webpush failed for user 33333333-…: 403 Forbidden — the VAPID credentials in the authorization header do not correspond to the credentials used to create the subscriptions.`
- **Cause (confirmed):** the frontend and the backend on DEV use keys from **different pairs**.
  - Deployed frontend `VITE_VAPID_PUBLIC_KEY` = `frontend/.env.development` value (`BPulOHH…`)
  - Dev backend `VAPID_PRIVATE_KEY` (`~/deploy/.env.dev` on EC2 = `infra/deploy-dev/.env.dev`) does **not** derive that public key
  - `backend/src/envs/.env.local` **does** match it, which is why it worked locally
- **Fix options:**
  - Fastest: put the `.env.local` VAPID private key into `~/deploy/.env.dev` (and `infra/deploy-dev/.env.dev`), then `docker compose up -d`. Existing subscriptions start working right away
  - Or: generate the frontend public key from the dev private key, then rebuild the frontend. Every device must toggle push off/on again, because subscriptions are bound to the old key
- **Side note:** 403 responses aren't cleaned up (only 404/410 are), so subscriptions made with a wrong key stay in the table and fail on every event.

---

## #6 — Lalamove Portal: "Destination host unreachable" when registering the webhook
- **Found:** 2026-10-12, registering `https://api-dev.sariko.store/rest/v1/deliveries/webhook` for the sandbox key
- **Actual:** Portal says "Destination host unreachable". No delivery status ever reaches DEV (order `21939402` auto-booked at 20:06, no webhook followed)
- **Cause (confirmed from dev logs):** the host *is* reachable. nginx shows `POST /rest/v1/deliveries/webhook` from `52.76.164.226` with UA `LalamoveAPI/3.0` at 20:10:19 and 20:10:35, both **401**. The backend logs `Webhook: apiKey mismatch (...)` with an empty apiKey. Lalamove's verification request carries no `apiKey`/`signature`, and `backend/src/apis/deliveries.py` (~L122) rejects it with 401. Lalamove needs a 200 to accept the URL and reports anything else as "unreachable".
- **Fix idea:** before the apiKey check, return 200 without touching the DB when the body has no `apiKey` and no `signature` (the verification ping). Real events still need a valid apiKey + HMAC.
- **Note:** `CLAUDE.md` still mentions `LALAMOVE_MODE (mock|live)`. The mock is gone, and DEV calls the real Lalamove sandbox.
