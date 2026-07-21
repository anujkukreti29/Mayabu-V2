# Mayabu v5.3 Upgrade Guide

No database migration is required for v5.3.

## 1. Replace the application files

Use the full v5.3 package for a clean update, or apply the backend patch package
over the existing v5.2 React/Vite package.

## 2. Update `.env`

Add:

```env
MAYABU_API_THREADPOOL_TOKENS=40
MAYABU_SCRAPER_DISTRIBUTED_SLOT_TTL_SECONDS=180
MAYABU_SCRAPER_DISTRIBUTED_SLOT_WAIT_SECONDS=5
```

The older `MAYABU_LIVE_VERIFY_DISTRIBUTED_SLOT_*` names remain accepted as
fallback aliases, but new deployments should use the generic scraper names.

## 3. Install and validate

From the project root in Windows CMD:

```cmd
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
python -m compileall -q mayabu mayabu_db mayabu_refresh
ruff check mayabu mayabu_db mayabu_refresh tests
pytest -q
```

Frontend:

```cmd
cd frontend
npm ci
npm run typecheck
npm run lint
npm run test
npm run build
```

## 4. Restart services

```cmd
docker compose --profile app up -d --build
```

## 5. Verify operations

Check `/api/health` and confirm:

- database is `ok`;
- Redis is `ok` in production;
- search mode is `v5_indexed` after v5 migrations;
- API worker, threadpool, and DB-pool values match the deployment plan.

Before scaling worker replicas, read `docs/PRODUCTION_TOPOLOGY.md` and run the
staging load-validation checklist.
