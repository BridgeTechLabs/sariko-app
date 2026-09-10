# Sariko — Filipino Homemade Food Marketplace

![Status](https://img.shields.io/badge/Status-MVP-blue)
![Node](https://img.shields.io/badge/Node-22.16-green)
![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/License-Proprietary-lightgrey)

## 📱 Project Overview

**Sariko** is a multi-vendor marketplace platform for Filipino homemade food products in Ho Chi Minh City (HCMC). It connects food sellers with local buyers through an intuitive mobile-first PWA.

**This repository includes:**
1. **Buyer App** (`/frontend`) — Vue 3 PWA for browsing, ordering, and payment
2. **Seller Dashboard** (within buyer app, `/seller/*` routes) — Menu & order management
3. **Quê Tôi** (`/frontend-quetoi`) — Second-tenant mock clone (Vietnamese community in Seoul)
4. **Landing page** (`/landing`) — Static marketing site
5. **Admin Panel** (separate repo) — Seller payouts & marketplace analytics, linked only through the Admin Gateway endpoints

## 🎯 Key Features

### Buyer App
- 🏪 Browse sellers & food items, with per-item variants and pricing
- 🔍 Search across sellers and dishes
- 🛒 Smart cart with single-seller constraint and live delivery quotation
- 💳 VNPay payment (create → redirect → IPN → return)
- 🚚 Order tracking with delivery timeline & driver info
- ⭐ Order reviews & ratings
- 💬 Buyer ↔ seller chat
- 📍 Address autocomplete & map pin (Goong Maps, proxied via backend)
- 🌐 Multi-language (English `en-PH`, Vietnamese `vi`)
- 🚀 Progressive Web App (installable)

### Seller Dashboard
- 📊 Order workflow: `pending → confirmed → ready → done`, plus cancel with reason
- 🍽 Menu management — categories, food items, variants, image upload
- 🚚 Auto-book Lalamove delivery when an order is marked ready
- 💬 Chat with buyers
- 📈 Dashboard stats & earnings summary

### Platform / Compliance
- 💰 **Admin Gateway** — refund & payout endpoints under `/rest/v1/admin/*`, consumed by the separate admin repo (`X-Api-Key` auth)
- 📋 **MOIT reporting** — Vietnam Ministry of Industry & Trade compliance endpoints

> **Note on "real-time":** order and delivery updates use polling (`composables/createPoller.js`, 10–15s, auto-stops on terminal states), not websockets.

---

## 🛠 Tech Stack

### Frontend
- **Framework**: Vue 3 (Options API)
- **Build**: Vite
- **UI**: Quasar Framework
- **State**: Pinia (+ `pinia-plugin-persist`)
- **Routing**: Vue Router (`src/plugins/router.js`)
- **i18n**: vue-i18n — `en-PH`, `vi`
- **Icons**: Lucide Vue Next
- **Maps**: Leaflet rendering Goong Maps data

### Backend
- **API**: FastAPI (Python 3.11)
- **Database**: PostgreSQL via Supabase PostgREST (no ORM — DAO layer)
- **Auth**: Supabase JWT verified against JWKS (ES256), `Depends(verify_token)`
- **Integrations**: VNPay (payments), Lalamove (delivery), Goong (maps/geocoding), MOIT (compliance)

### Infrastructure
- Docker image built & pushed on merge to `main` (GitHub Actions, self-hosted EC2 runner)
- nginx reverse proxy + certbot TLS (`infra/docker/`)
- Readiness check with automatic rollback on failed deploy

---

## 📂 Project Structure

```
sariko-app/
├── frontend/                    # Vue 3 + Quasar PWA (buyer + seller)
│   ├── src/
│   │   ├── pages/              # Route-level pages (+ auth/, seller/)
│   │   ├── layouts/            # Page layouts (own padding/positioning)
│   │   ├── components/         # Feature-grouped components
│   │   ├── stores/             # Pinia stores
│   │   ├── apis/               # Axios API clients, grouped by domain
│   │   ├── composables/        # createPoller, setLanguage
│   │   ├── plugins/            # router.js, i18n.js, pinia.js, quasar.js
│   │   ├── lib/                # supabase.js, axiosPolicy.js (token injection)
│   │   ├── utils/              # priceDisplay, fileToBase64
│   │   ├── i18n/locales/       # en-PH.json, vi.json
│   │   └── assets/             # SCSS variables & resources
│   ├── .env.example
│   └── vite.config.js
│
├── backend/                     # FastAPI backend
│   ├── src/
│   │   ├── main.py             # App, CORS, router registration
│   │   ├── lifespan.py
│   │   ├── apis/               # Routers: cart, orders, sellers, payments,
│   │   │                       #   deliveries, chat, reviews, search, users,
│   │   │                       #   address, admin_refunds, moit, dev
│   │   ├── dao/                # Data access layer (all DB access goes here)
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── core/               # auth.py (JWKS verify), phone, display_name
│   │   ├── clients/            # supabase.py
│   │   ├── services/           # lalamove_service, supabase_realtime
│   │   ├── utils/              # pricing, storage, image_compressor
│   │   ├── sql/                # Schema — see sql/README.md
│   │   └── envs/.env.example
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend-quetoi/             # Quê Tôi tenant — mock-adapter clone
├── landing/                     # Static landing page
├── infra/docker/                # compose.yaml, nginx, get_cert.sh
├── tests/                       # backend (pytest), frontend, smoke, manual
├── .github/workflows/main.yml   # Test → build → deploy → rollback
├── BACKEND_APIS.md              # Endpoint reference
├── CLAUDE.md                    # Development guidelines
└── README.md                    # This file
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js 22.16 / npm 10.9 (see `frontend/package.json` → `engines`)
- Python 3.11
- A Supabase project

### Installation

**1. Clone & install dependencies**
```bash
git clone git@github.com:yellowchicken2111/sariko-app.git
cd sariko-app

# Frontend
cd frontend && npm install

# Backend
cd ../backend && pip install -r requirements.txt
```

**2. Environment Setup**

```bash
cp frontend/.env.example frontend/.env.development
cp backend/src/envs/.env.example backend/src/envs/.env.local
```

Fill in both files — every value is blank in the template. The backend loads
`envs/.env.$ENV`, and `ENV` defaults to `local`. The `/dev` helper router is
only mounted when `ENV` is `local` or `dev`.

Never commit a filled-in copy: `.env*` is gitignored (the two `.env.example`
templates are the only exceptions).

**3. Database Setup**

Paste the whole of `backend/src/sql/master.sql` into the Supabase SQL Editor and
run it once. `master.sql` is generated — edit the sources under `sql/tables/`,
`sql/functions/`, or `sql/policies/` and regenerate with `./build_master.sh`.
See [`backend/src/sql/README.md`](backend/src/sql/README.md) for the schema
layout, dependency order, and known issues.

### Development

**Terminal 1 — Frontend**
```bash
cd frontend
npm run dev
# Runs on http://localhost:8081
# Proxies /rest → http://localhost:5000
```

**Terminal 2 — Backend**
```bash
cd backend/src
python main.py
# Runs on http://localhost:5000
```

Open http://localhost:8081 in your browser.
Dev panel (force-pay / force-status): `Ctrl+Shift+Q`.

### Tests
```bash
pytest tests/backend -v     # unit + integration (also run in CI)
```
Smoke-test checklist: [`tests/smoke/DEPLOY_SMOKE_TEST.md`](tests/smoke/DEPLOY_SMOKE_TEST.md)

---

## 📡 API

All endpoints are served under `/rest/v1/`. In development the Vite proxy maps
`/rest` → `http://localhost:5000`.

| Group | Purpose |
|-------|---------|
| Users / Auth | Profile, address, password |
| Sellers | Discovery, menu, seller-side order & menu management |
| Cart | Add / update / remove items |
| Orders | Create, view, cancel |
| Payments | VNPay create, IPN (public), return (public) |
| Deliveries | Quotation, status, webhook, cancel |
| Chat | Conversations & messages |
| Reviews | Order reviews & ratings |
| Search | Cross-entity search |
| Address | Goong search / detail / reverse geocode |
| Admin Gateway | Refunds & payouts for the admin repo (`X-Api-Key`) |
| MOIT | Compliance reporting |
| Dev | Local-only test helpers (`ENV=local\|dev` only) |

Full endpoint reference: [`BACKEND_APIS.md`](BACKEND_APIS.md).
Interactive docs at `http://localhost:5000/docs` while the backend runs.

---

## 🗄 Database

PostgreSQL (Supabase) covering user accounts, seller profiles & menus (with item
variants), carts, orders, payments, deliveries, refunds, payouts, reviews, chat,
and admin configuration.

Schema, functions, and RLS policies live in
[`backend/src/sql/`](backend/src/sql/).

Image uploads go through backend endpoints using the service role, **not** direct
client uploads to Supabase Storage — `auth.uid()` is null in the storage-api
context under this project's ES256 JWTs.

---

## 🌍 Deployment

Merges to `main` trigger `.github/workflows/main.yml` on a self-hosted EC2
runner: run `pytest tests/backend` → build & push the Docker image →
`docker compose pull && up -d` → readiness check with automatic rollback to the
previous image tag on failure.

nginx terminates TLS and reverse-proxies the API; VNPay IPN source-IP filtering
is enforced there (`infra/docker/nginx/nginx.conf`), not in the app.

### Build
```bash
# Frontend
cd frontend && npm run build

# Backend
cd backend && docker build -t sariko-backend .
```

---

## 📞 Support

For issues, questions, or feedback:
- Open an issue on GitHub
- Check existing issues before creating duplicates
- Follow the issue template

---

## 📝 License

**Proprietary — All rights reserved.**
This source code is not licensed for redistribution, modification, or
commercial reuse. Contact the Sariko team for permissions.

---

## 🙏 Acknowledgments

- **Quasar Framework** for Vue 3 components
- **FastAPI** for Python backend framework
- **Vite** for fast frontend build tooling

---

**Built by Sariko Team**
HCMC, Vietnam 🇻🇳
