# Bug Notes

Bugs found during manual testing. Newest at the bottom.

- **Status:** ⬜ Open · 🔧 Fixed in branch (not deployed) · ✅ Verified on DEV
- **Deployed:** which env runs the fix (`—` = nowhere yet), plus branch / commit

| # | Bug | Status | Deployed |
|---|-----|--------|----------|
| 1 | Buyer address toast on login (DEV missing migration) | 🔧 Migrations `20261003…` + `20261009…` applied on DEV by pipeline, columns exist. UI check pending (no toast on login) | DEV `5067e95` (2026-10-12) |
| 2 | Seed `'vi'` ≠ `'Tiếng Việt'` → English pushes | 🔧 Seed fixed in `fix/common-bugs` ('English' / 'Tiếng Việt'); existing DEV rows need the one-off SQL below | DEV `5067e95` (2026-10-12) |
| 3 | VNPay "Sai chữ ký" (`vnp_IpnUrl`) | 🔧 DEV env fixed (verified code 24 = buyer cancel); code trap removed in `fix/common-bugs` (`vnp_IpnUrl` + `VNPAY_IPN_URL` deleted) | DEV `5067e95` (2026-10-12) |
| 4 | Push enable fails silently (Brave) | 🔧 Fix in `fix/common-bugs`: toast `account_v2.push_failed` with the Brave hint | DEV `5067e95` (2026-10-12) |
| 5 | DEV pushes 403: VAPID key pair mismatch | ✅ Verified on DEV: keys rotated, seller re-subscribed, notifications arrive (FCM 201) | DEV backend `e6aac52`+ |
| 6 | Lalamove can't register webhook ("Destination host unreachable") | ✅ Verified on DEV: webhook `COMPLETED` → order `21939402` done (20:18 UTC) | DEV backend `29be3bd` |
| 7 | Order list badges ignore Lalamove delivery status (buyer + seller) | 🔧 Fix in `fix/common-bugs`: lists embed `deliveries(status)`, webhook touches order + drops seller cache, `/seller/orders` now polls | DEV `5067e95` (2026-10-12) |
| 8 | Seller order detail: back button does nothing | 🔧 Fix in `fix/common-bugs`: `backTo="/seller/orders"` (same as buyer detail) | DEV `5067e95` (2026-10-12) |
| 9 | "Ready for delivery" gated to delivery time + countdown (seller request) | 🔧 Built in `fix/common-bugs`: 45 min window, FE disabled + "Ready in 1h 20m", BE 400 if early, no override | DEV `5067e95` (2026-10-12) |
| 10 | Menu management: can't switch a dish from pre-order to instant | 🔧 Redesigned in `fix/common-bugs`: Pre-order switch (off = instant 0, on = days ≥ 1, default 1) | DEV `5067e95` (2026-10-12) |
| 11 | Seller can't rename their store | 🔧 Built in `fix/common-bugs`: "Tên cửa hàng" in Hồ sơ (sellers only), slug unchanged, 1–50 chars | DEV `5067e95` (2026-10-12) |
| 12 | Seller Me page: "Edit Profile" and "My Profile" duplicate | 🔧 Fix in `fix/common-bugs`: removed the Settings row, kept the header button + avatar | DEV `5067e95` (2026-10-12) |
| 13 | Coming-soon kitchens look the same as open ones in seller lists | 🔧 Fix in `fix/common-bugs`: muted (50% + grayscale) card | DEV `5067e95` (2026-10-12) |
| 14 | Seller can't open/close their store | 🔧 Built in `fix/common-bugs`: switch + daily hours on seller Home; closed/outside hours blocks same-day only; lists Open → Closed → Coming soon | DEV `5067e95` (2026-10-12) |
| 15 | Onboarding / legacy address form: saving a first address → 500 (NOT NULL receiver) | 🔧 Fix in `fix/common-bugs`: insert defaults receiver to account holder | DEV `820ac47` (2026-10-12) |
| 16 | Prod deploy never runs: prod runner registered to the old repo; DEV runner also carries the prod label | ✅ Runner re-registered + DEV label removed; run attempt 3 on `ec2-sariko-app` → prod `1f9f04f` | PROD `1f9f04f` (2026-10-12) |

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
- **Fixed (2026-10-12):** the seed now writes the app's values (`'English'` / `'Tiếng Việt'`, from `frontend/src/composables/setLanguage.js`). Seeds only run on `db reset`, so existing DEV rows (2× `vi`, 2× `en-PH`) need:
  `update users set preferred_language = case preferred_language when 'vi' then 'Tiếng Việt' else 'English' end where preferred_language in ('vi','en-PH');`

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
- **Status (2026-10-12):** Jack removed `VNPAY_IPN_URL` from the dev env. Verified the container no longer has it, and nginx shows a VNPay return at 20:33 UTC with `vnp_ResponseCode=24` (buyer cancelled on the VNPay page), so the signature is accepted. The `if VNPAY_IPN_URL` lines in `payments.py` are still in the code: setting the variable anywhere breaks checkout again.

---

## #4 — Enabling push fails silently (e.g. on Brave)
- **Found:** 2026-10-12, enabling push notifications on app-dev with Brave
- **Actual:** The toggle flips back to Off with no message. No row is written to `push_subscriptions`
- **Expected:** A toast explaining that push couldn't be enabled on this browser
- **Cause (very likely, not yet confirmed in console):** Brave disables Web Push by default (Chromium push goes through Google FCM). `pushManager.subscribe()` throws, and `togglePush` in `frontend/src/stores/v2/account/accountStore.js` (~L243-262) only `console.warn`s inside `catch`. Only the `unsupported`/`blocked` results show a toast.
- **Fix idea:** In the `catch`, show the same negative Notify (e.g. reuse `account_v2.push_unsupported` or add a "couldn't enable, check browser settings" message).
- **Status (2026-10-12):** push works end to end on Chrome. This entry is now only about the missing error message for browsers where subscribing throws.
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

---

## #7 — Order list badges don't follow the Lalamove delivery status
- **Found:** 2026-10-12, buyer order history + seller order list
- **Actual:** The badge stays `Ready` while Lalamove goes ASSIGNING_DRIVER → ON_GOING → PICKED_UP, and only changes at `done` (COMPLETED)
- **Expected:** The badge reflects delivery progress (e.g. "Finding driver", "Driver on the way", "Picked up")
- **Cause (from code):** this is a missing feature, not a broken one. The badge only reads `orders.status` (`frontend/src/components/order-history/OrderCard.vue` L30-44, `components/seller-orders/SellerOrdersList.vue`). Lalamove progress lives in the `deliveries` table, which the list queries don't join (`backend/src/dao/dao_orders.py` `read_orders_by_user_id`, `read_orders_by_seller_id`). Only the order detail page (DeliveryTracker) shows it.
- **Fix (2026-10-12):** list queries embed `deliveries(status)`; `frontend/src/utils/deliveryBadge.js` shows "Tìm tài xế / Đang đến / Đã lấy hàng" (`delivery_tracker.status_*`) while the order is `ready`; the webhook calls `DAOOrders.touch_order()` (bumps `updated_at` via the `on_orders_update` trigger + invalidates the seller cache); `SellerOrdersList` now starts the refcounted seller poller (before, `/seller/orders` fetched once and never refreshed).
- **Watch out when fixing:** the seller list uses a HEAD/`updated_at` cache signature on `orders` (`read_orders_head_by_seller_id`). Webhook updates only touch `deliveries`, so the seller list would *not* refresh even after joining deliveries, unless the webhook also bumps `orders.updated_at` / invalidates the cache.

---

## #8 — Seller order detail: back button doesn't work
- **Found:** 2026-10-12
- **Where:** `frontend/src/pages/seller/SellerOrderDetailPage.vue` → `components/shared/PageBreadcrumbs.vue` `goBack()` → `$router.back()` (no `backTo` passed)
- **Suspected cause (unverified):** the page was opened from a **push notification**. `push-sw.js` `notificationclick` navigates or opens the window straight at `/seller/orders/{id}`, so there is no previous in-app history entry and `router.back()` does nothing. Opening the page from the order list probably works.
- **Repro to confirm:** open the detail from the list → back. Then open it from a notification → back.
- **Fix idea:** pass `back-to="/seller/orders"`, or in `goBack()` fall back to a route when `window.history.state?.back` is null (Vue Router sets it). The same issue likely hits the buyer `/orders/{id}` page opened from a push.

---

## #9 — 💡 Seller request: "Ready for delivery" only when it's time, with a countdown
- **Found:** 2026-10-12 (seller feedback)
- **Today:** Ready is always clickable (`components/seller-order-detail/SellerOrderActionBar.vue`, `components/seller-home/ActionOrdersList.vue`). Marking Ready auto-books Lalamove immediately, so an early tap books a driver hours before a scheduled `delivery_appointment`.
- **Request:** for orders with `delivery_appointment`, disable Ready until a window before the appointment and show the time remaining (e.g. "Available in 1h 20m").
- **Decisions needed (Jack):**
  - How early may the seller tap Ready (e.g. 30 / 45 / 60 min before)? It should cover cooking + Lalamove driver search time.
  - Frontend-only gate, or also reject early `ready` in the backend (`PATCH /sellers/me/orders/{id}/status`)?
  - Is an emergency override needed (the seller finished early, or the buyer asks for earlier)?
- **Decided (2026-10-12):** 45 min · frontend + backend · no override · orders without an appointment are unchanged.
- **Built:** `backend/src/apis/sellers.py` `READY_WINDOW` + `ready_opens_at()` (400 when early, test `tests/backend/unit/test_ready_window.py`); `frontend/src/utils/readyWindow.js` (`READY_WINDOW_MINUTES` must match the backend); button disabled with a countdown in `SellerOrderActionBar.vue` (detail) and `ActionOrdersList.vue` (seller home), refreshed every minute.

---

## #10 — Menu management: can't switch a dish from pre-order to instant
- **Found:** 2026-10-12
- **Where:** `frontend/src/components/seller-menu/ModalEditItem.vue` (`preorder_day` number input, L291-292; payload L134) → `PATCH` handler in `backend/src/apis/sellers.py` `update_food_item` (`model_dump(exclude_none=True)`)
- **Not the cause:** the backend keeps `preorder_day = 0` (`exclude_none` only drops `None`), and the schema allows `ge=0`.
- **Suspect (unverified):** if the seller *clears* the field instead of typing `0`, `v-model.number` sends `""`, so the backend returns 422 and nothing is saved. There is also no explicit "Instant" switch, so "instant = 0 pre-order days" isn't obvious.
- **Repro needed:** what exactly did the seller do (clear the field / type 0 / another screen called "management")? Was there an error toast?
- **Confirmed mechanism (2026-10-12):** `RequestUpdateFoodItem(preorder_day="")` → pydantic `int_parsing` error (422). Vue `.number` keeps a cleared input as `""`. Typing `0` saves fine. Fix: `preorder_day: Number(...) || 0` in the payload.
- **Redesign (Jack, 2026-10-12):** replaced the raw "days" input with a **Pre-order switch**. Off = instant (`preorder_day = 0`, input hidden). On = days input shown, defaults to 1, payload clamps to ≥ 1. `is_preorder` is UI-only, derived from `preorder_day > 0`, and not sent to the API.
- **Same risk, not fixed:** `min_quantity` and `quantity_step` in the same payload also send `""` when cleared → 422.

---

## #11 — 💡 Seller can't change their store name
- **Found:** 2026-10-12
- **Today:** nothing writes `seller_profiles.store_name` after onboarding. Seller "Hồ sơ của tôi" → `/account/profile` (`components/account/ProfileForm.vue`) → `PATCH /users/me/profile` (`backend/src/apis/users.py`) only syncs `phone/address/lat/lon` (+ avatar) to `seller_profiles` (`DAOSellerProfiles.update_seller_profile_info` allow-list).
- **Watch out:** `slug` (unique, used in `/seller/:slug` and the seller share card/QR) is separate from `store_name`. Renaming must not silently change the slug, or shared links break.
- **Decided (2026-10-12):** keep the slug · field in "Hồ sơ của tôi" · no approval, validate only (trimmed, 1–50 chars).
- **Built:** `RequestUpdateProfile.store_name` (`StringConstraints`, test `tests/backend/unit/test_store_name.py`) → `users.py` routes it to `seller_profiles` with phone/address → `DAOSellerProfiles` allow-list. `ProfileForm.vue` shows the field only when `user.isSeller`, loads it from `dashboardStore.sellerInfo` (fetching if needed), and updates the store after saving. Buyers sending `store_name` are ignored (the users DAO uses an allow-list).

---

## #12 — Seller Me page: "Edit Profile" and "My Profile" are duplicates
- **Found:** 2026-10-12
- **Cause:** both open `/account/profile`: the header button + avatar (`components/seller-me/SellerMeHeader.vue`) and a Settings row (`components/seller-me/SellerMeSettings.vue`).
- **Fix:** removed the Settings row, its `User` icon import and the now-unused `seller_me.menu_label_profile` i18n key. The header "Edit Profile" button (and avatar tap) stay as the single entry point.

---

## #13 — Coming-soon kitchens should look muted; open ones first
- **Found:** 2026-10-12
- **Order:** already correct. `DAOSellerProfiles.read_founding_sellers` orders by `status` (`active` < `coming_soon`), then `display_order`, then `created_at`. On DEV: Rosa (active) is before Ben (coming_soon).
- **Fix:** `components/seller/seller-list/SellerCard.vue` adds a `.muted` class (opacity 0.5 + grayscale) when `status === 'coming_soon'`. The card stays tappable and opens the coming-soon page.
- **Follow-up (2026-10-12, Jack):** dimmer (opacity 0.3) and **not tappable** from the lists (`onClicked` returns early, default cursor). The coming-soon page still opens from a direct link.

---

## #14 — 💡 Seller open/closed switch
- **Found:** 2026-10-12
- **Today:** `seller_profiles.is_open` (bool, default true), `opening_time`, `closing_time` exist since the initial schema, but nothing uses them. Only `GET /sellers/{slug}` selects them, and no UI reads them. Buyers can order from any active seller at any time.
- **Decided (2026-10-12):** manual switch · closed blocks same-day dishes only (pre-orders still OK) · lists: open → closed (badge, not muted) → coming soon (muted) · closing only stops new orders, with a warning if orders are still active.
- **Built:**
  - Backend: `PATCH /sellers/me/open` (`RequestSetStoreOpen`), `GET /sellers/me` returns `is_open`; `/sellers/founding` orders by status, then `is_open` desc. Gate on `POST /cart/add` (`DAOFoodItems.read_order_gate`) **and** `POST /orders` (items added before closing), sharing `STORE_CLOSED_DETAIL` / `is_same_day` in `apis/orders.py`. Tests: `tests/backend/integration/test_store_closed.py`.
  - Frontend: Open/Closed toggle in `SellerGreeting.vue` (confirm dialog when active orders exist); `utils/storeOpen.js` `blockedByClosedStore()` disables add in `FoodCard.vue` + `BottomActionBar.vue` ("Cửa hàng đang đóng"); `SellerInfo.vue` closed notice; `SellerCard.vue` "Đã đóng" badge.
  - Side fix: `cartStore.addItem` now returns true/false. `FoodCard`, `FeaturedDishCard` and `BottomActionBar` used to show "added to cart" even when the add failed.
- **Before prod deploy:** check `select store_name from seller_profiles where status='active' and is_open is false;` on prod. Any row becomes "closed" the moment this ships (the column was never shown before).
- **Opening hours (2026-10-12):** one daily window for every day, switch = master. No scheduler: "open now" is computed on read in `backend/src/core/store_hours.py` `is_open_now()` (VN time, UTC+7 fixed; overnight windows; same open/close = 24h; no hours = all day; tests `tests/backend/unit/test_store_hours.py`). Buyer-facing reads (`read_founding_sellers`, `read_seller_by_slug_name`) replace `is_open` with the computed value, so the buyer frontend didn't change. Cart/order gates use it too. Seller: `PATCH /sellers/me/hours` (`RequestSetStoreHours`, both-or-neither), and `GET /sellers/me` returns the raw switch + hours + `open_now`. Hours editor and an "outside hours" hint live in `SellerGreeting.vue`.
- **Prod check (2026-10-12, Jack):** no seller has `opening_time` set, and no active seller has `is_open = false`. Deploy changes no store's visible state.
- **Known limit:** the seller's own "outside hours" hint uses `open_now` from the last fetch, so it updates on reload, not exactly at opening time. Buyers are always computed live.

---

## #15 — First address save fails after migration 20261003 (NOT NULL receiver fields)
- **Found:** 2026-10-12, while reviewing the migration before applying it to prod. Not reported by a user. No DEV buyer was affected (none signed up since the migration ran).
- **Cause:** `20261003015158_add_new_columns_to_user_addresses.sql` makes `receiver_name` / `phone_number` NOT NULL. `PATCH /users/me/profile` with `address` (buyer onboarding `components/onboarding/buyer/ButtonGroup.vue`, legacy `components/account/AddressForm.vue`) → `DAOUserAddresses.upsert_default_address` inserts **without** them → 500. Onboarding swallows the error and moves on, so the buyer finishes onboarding with **no saved address**.
- **Fix:** the insert branch of `upsert_default_address` defaults both fields to the account holder's `users.name` / `users.phone` (same rule as the migration backfill). `users.py` also passes `body.name` / `body.phone`, since onboarding sends the phone in the same request, before `users` is updated. Tests: `tests/backend/unit/test_default_address_insert.py`.
- **Prod:** must ship together with the prod migration (see the release notes in chat). The old prod backend has this same bug once the migration is applied.

---

# Prod release checklist (develop → main)

Prod migration history ≠ repo (only `20260916144935` recorded), so **never `supabase db push` prod**. Apply migrations by hand.

**Pre-checks done (2026-10-12, Jack, on prod):**
- [x] No `opening_time` set on any seller; no active seller with `is_open = false` → deploy changes no store's visible state
- [x] `user_addresses` has none of `receiver_name/phone_number/note/street_name/updated_at`; 0 orphan addresses → `20261003…` will apply cleanly
- [x] `push_subscriptions` already exists on prod, created by hand identical to DEV → `20261009…` not needed

**Before release:**
- [x] #15 fix merged to `develop` (PR #36) and deployed to DEV `820ac47`
- [ ] UI checklist on DEV passed (all 🔧 → ✅)
- [x] Prod backend already has its own `VAPID_PRIVATE_KEY` (in `~/deploy/.env`, a different pair from DEV/local, checked 2026-10-12)
- [x] (superseded: Jack generated a new prod pair) Prod frontend build: `VITE_VAPID_PUBLIC_KEY=BOqom0UmgeisCjX6R2NuVpN-RC-9BurXpMkMEz9rHQwkzTF37xPfIlpxucOthIXz_QeRzTuDZxSngZJOU7NsaPA` (derived from the prod private key; a mismatch = 403 on every push, see #5)
- [x] `prd-deploy-pipeline.yml` now writes running tags to `~/deploy/image_tags.env` (**not** `.env`: on prod that file is the backend env_file with all secrets) and cleans old images; no migration step
- [ ] Lalamove: webhook URL `https://api.sariko.store/rest/v1/deliveries/webhook` registered for the **production** API key
- [ ] Prod env must NOT contain `VNPAY_IPN_URL` (#3)

**Release (back to back):**
1. [x] Prod SQL editor: ran `20261003015158_add_new_columns_to_user_addresses.sql` in a transaction (2026-10-12, Jack). Verified: 15 addresses, 0 empty receivers
2. [x] Merged (PR #37). After fixing #16, attempt 3 deployed on the prod runner (22:36 UTC). The window with the new schema + old backend lasted roughly 22:30–22:36 UTC.

**After release (smoke):**
- [ ] Buyer login: no address error toast; new buyer onboarding saves an address
- [ ] Enable push on Chrome → row in `push_subscriptions`; force a paid order → seller notified
- [ ] Seller open/closed switch + hours visible on seller Home

**Prod server notes (seen 2026-10-12, not changed):**
- `~/deploy/compose.yaml` on prod has no `restart: unless-stopped` (dev has it). After an EC2 reboot the backend, nginx and certbot won't come back by themselves.
- Prod backend publishes `"5000:5000"` (dev binds `127.0.0.1:5000`). It's not reachable from outside today (Security Group blocks it). Binding to 127.0.0.1 would keep it that way even if the SG changes.
- Disk 55% (10G/19G), 6 backend images, 3.3 GB build cache (2.2 GB reclaimable). The new cleanup step handles this from the next deploy.
- `VNPAY_IPN_WHITELIST` comment in prod `.env` says "Sandbox IPs below": check before VNPay go-live.

---

## #16 — Prod pipeline never runs: self-hosted runner registered to the old repo
- **Found:** 2026-10-12, after PR #37 (develop → main) merged. Prod still ran `1e62d29` (Oct 8) and had no `image_tags.env`.
- **Cause (confirmed):** prod EC2 `~/actions-runner/.runner` → `gitHubUrl: https://github.com/yellowchicken2111/sariko-app` (service `actions.runner.yellowchicken2111-sariko-app.ec2-sariko-app`). The repo now lives at `BridgeTechLabs/sariko-app`. The DEV runner was re-registered there, but prod wasn't. The job (`runs-on: ec2-sariko-app`) waits in Queued with no runner to take it. The last job the prod runner ran was 2026-10-08 15:10.
- **Fix:** re-register the prod runner to `BridgeTechLabs/sariko-app` with label `ec2-sariko-app` (token from GitHub → repo Settings → Actions → Runners → New self-hosted runner). Then re-run the queued workflow. Also check that the `production` environment in the BridgeTechLabs repo has `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`.
- **Update (2026-10-12):** prod runner re-registered to BridgeTechLabs (service `actions.runner.BridgeTechLabs-sariko-app.ec2-sariko-app`, online). But GitHub had **already run the prod job (run for `1f9f04f`, "success") on the DEV runner `ec2-sariko-app-dev`**, because that runner also carries the label `ec2-sariko-app`. Effects on DEV: backend redeployed as `1f9f04f` (same backend code as `820ac47`, healthy), `.env.dev` intact, a stray `~/deploy/image_tags.env` written, and old dev images cleaned. Prod untouched (still `1e62d29`). Luckily the prod pipeline has no migration step.
- **Must fix before re-running:** GitHub → Settings → Actions → Runners → `ec2-sariko-app-dev` → remove the label `ec2-sariko-app`, so it keeps only `ec2-sariko-app-dev` (+ default self-hosted labels). Otherwise any prod job can land on DEV again.

**Post-release verification (2026-10-12 22:40 UTC, Claude, read-only):**
- Prod backend `1f9f04f` healthy, `/health` 200, no exceptions in the logs since start
- `~/deploy/image_tags.env` = `PREV_IMAGE_TAG=1e62d29` / `IMAGE_TAG=1f9f04f`; `~/deploy/.env` intact (20 keys, no `VNPAY_IPN_URL`)
- Cleanup ran: backend images 6 → 2, disk 55% → 45%, build cache 3.3 → 1.7 GB
- `/sellers/founding` returns `is_open` (3 sellers, all open)
- VAPID: the `app.sariko.store` bundle key `BFHAUE9N…` **matches** the running prod backend private key
- ⚠️ `https://sariko.store` (apex) fails the TLS handshake (`sslv3 alert handshake failure`), while `www.sariko.store` → 200 and `app.sariko.store` serves today's build. Check the Cloudflare SSL/DNS setup for the apex (LINKS.md lists sariko.store as the marketplace PWA).
- [ ] Still to smoke-test by hand on prod: new buyer onboarding saves an address (#15), push on Chrome, seller open/closed + hours
