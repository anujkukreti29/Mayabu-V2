# Mayabu v5.3 to v5.4 Manual Upgrade Guide

This upgrade is designed for file-by-file application. It does not require a
database migration.

## 1. Back up the current baseline

From Windows CMD in the project parent directory:

```cmd
xcopy mayabu_v5_3_fullstack_production mayabu_v5_3_backup\ /E /I /H
```

Do not copy `.venv`, `frontend\node_modules`, build output, caches, logs, or
artifacts into the backup if disk space is limited.

## 2. Apply backend foundation files first

Replace or add these files in this order:

```text
.env.example
mayabu\core\config.py
mayabu\core\distributed_limit.py
mayabu\scrapers\capacity.py                 (new)
mayabu\jobs\worker.py
run_mayabu_db.py
run_refresh_price.py
scraper_health_check.py
```

These files establish shared scraper capacity, renewable leases, and the new
configuration defaults. Keep the group together; do not update only
`worker.py` without adding `capacity.py`.

## 3. Apply matching and logging refinements

```text
mayabu\domain\matching.py
mayabu\search\query_parser.py
mayabu\api\search_routes.py
mayabu_db\repository.py
mayabu_refresh\amazon.py
mayabu_refresh\flipkart.py
mayabu_refresh\croma.py
mayabu_refresh\reliancedigital.py
mayabu\__init__.py
```

## 4. Apply frontend files

Replace `package.json` and `package-lock.json` together, then run `npm ci`.
Recharts is intentionally removed.

```text
frontend\package.json
frontend\package-lock.json
frontend\app\lib\api\client.ts
frontend\app\lib\content\trust.ts            (new)
frontend\app\lib\navigation\routes.ts        (new)
frontend\app\lib\pricing\statistics.ts       (new)
frontend\app\lib\pricing\insight.ts          (new)
frontend\app\lib\verification\state.ts
frontend\app\hooks\use-verification.ts
frontend\app\components\layout\header.tsx
frontend\app\components\layout\footer.tsx
frontend\app\components\pricing\price-history-chart.tsx
frontend\app\routes\product-detail.tsx
frontend\app\routes\sitemap[.]xml.ts
```

The brackets in `sitemap[.]xml.ts` are part of the filename.

## 5. Apply tests

```text
tests\test_v51_hardening.py
tests\test_v53_scale_safety.py
tests\test_v54_refinement.py                    (new)
frontend\app\lib\api\client.test.ts            (new)
frontend\app\lib\pricing\statistics.test.ts    (new)
frontend\app\lib\pricing\insight.test.ts       (new)
frontend\app\lib\verification\state.test.ts
frontend\app\components\pricing\price-history-chart.test.tsx  (new)
```

## 6. Update environment values only when needed

The defaults are safe for local development:

```env
MAYABU_WORKER_TASK_LEASE_MINUTES=20
MAYABU_WORKER_LEASE_REFRESH_SECONDS=120
MAYABU_SCRAPER_HEADLESS=true
MAYABU_SCRAPER_DEBUG=false
```

Keep debug false in normal operation. Enable it temporarily only while
investigating a retailer extraction problem.

## 7. Validate the backend

Working folder: project root.

```cmd
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
python -m compileall -q mayabu mayabu_db mayabu_refresh
ruff check mayabu mayabu_db mayabu_refresh tests run_mayabu_db.py run_refresh_price.py scraper_health_check.py
pytest -q
```

Expected current result without a PostgreSQL test database:

```text
47 passed, 1 skipped
```

## 8. Validate the frontend

Working folder: `frontend`.

```cmd
cd frontend
copy .env.example .env
npm ci
npm run typecheck
npm run lint
npm run format:check
npm run test -- --maxWorkers=6
npm run build
node scripts\verify-client-build.mjs
node scripts\verify-server-build.mjs
node scripts\verify-prerender.mjs
node scripts\verify-seo.mjs
```

## 9. Start the services

Use separate Windows CMD terminals.

API:

```cmd
scripts\start_api_windows.cmd
```

Worker:

```cmd
scripts\start_worker_windows.cmd
```

Frontend:

```cmd
cd frontend
npm run dev
```

## 10. Rollback

No schema rollback is needed. Stop the API, workers, and frontend, restore the
changed files from the backup, run `npm ci` in the restored frontend, and start
the services again.

Historical reports were moved into `docs\history` in the complete v5.4 package.
That organization change is optional when applying the patch manually and has
no runtime effect.
