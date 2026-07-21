# Mayabu v5.5 Refined Baseline

Mayabu is a modular FastAPI, PostgreSQL, Redis, Playwright, and React Router/Vite price-intelligence platform for Indian electronics.

Core rule: public search reads stored data and never starts live scraping. Discovery, refresh, direct ingestion, and user verification run through bounded durable workers.

## Baseline features

- Deterministic product identity with hard RAM, storage, CPU, screen, and model conflict rules.
- Exact matches, similar variants, and related products remain separate.
- PostgreSQL search documents, durable jobs, leases, retries, dead jobs, price observations, and audit data.
- Redis cache, rate limiting, request coalescing, and cross-replica platform capacity.
- Stored prices render immediately; verification is optional and non-blocking.
- React 19 + Vite + React Router SSR, hydration, prerendering, canonical URLs, and structured data.
- Strict TypeScript, Zod API validation, accessible responsive UI, deterministic tests, and CI.

## Start on Windows CMD

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
docker compose up -d postgres redis
python -m mayabu_db.migrate
```

API terminal:

```cmd
scripts\start_api_windows.cmd
```

Worker terminal:

```cmd
scripts\start_worker_windows.cmd
```

Frontend terminal:

```cmd
cd frontend
copy .env.example .env
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`.

## Validation

Backend:

```cmd
python -m compileall mayabu mayabu_db mayabu_refresh
python -m pytest -q
```

Frontend:

```cmd
cd frontend
npm ci
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
node scripts\verify-prerender.mjs
node scripts\verify-seo.mjs
```

## Documentation

- Architecture: `docs/BACKEND_ARCHITECTURE.md`
- Verification: `docs/LIVE_PRICE_VERIFICATION.md`
- Production topology: `docs/PRODUCTION_TOPOLOGY.md`
- Production checklist: `docs/PRODUCTION_CHECKLIST.md`
- v5.5 changes: `MAYABU_V5_5_REFINEMENT_REPORT.md`
- Manual update: `MAYABU_V5_5_MANUAL_UPGRADE_GUIDE.md`
- Historical reports: `docs/history/`

No database migration or public API change is required for v5.5.
