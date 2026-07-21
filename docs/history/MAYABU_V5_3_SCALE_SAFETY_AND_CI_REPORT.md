# Mayabu v5.3 Scale-Safety and CI Hardening Report

## Scope

Mayabu v5.3 is a focused backend hardening release built from the audited
`mayabu_v5_2_fullstack_react_vite_final.zip`. The React/Vite product frontend,
FastAPI contracts, PostgreSQL schema, matching engine, durable queue, cache
behavior, and live-verification model were preserved.

The release addresses the seven findings in the independent backend audit
without introducing an unnecessary framework or infrastructure rewrite.

## Implemented fixes

### F-1: distributed worker concurrency

Discovery, refresh, direct-ingestion, and live-verification tasks now acquire
one shared per-platform Redis lease. The lease:

- is enforced across worker processes and replicas;
- preserves the existing process-local semaphore as a first safety layer;
- renews itself while long discovery jobs are running;
- expires abandoned tokens automatically;
- fails closed in production when Redis coordination is configured but
  unavailable;
- uses the same platform budget for every scraper workload, so verification and
  scheduled scraping cannot independently exceed the retailer limit.

Primary files:

- `mayabu/core/distributed_limit.py`
- `mayabu/verification/platform_gate.py`
- `mayabu/jobs/worker.py`

### F-2: CI/CD regression protection

Added `.github/workflows/ci.yml` with three jobs:

1. Backend compile, Ruff, and pytest.
2. Frontend typecheck, lint, unit/component tests, SSR build, prerender, and SEO.
3. Deterministic Playwright E2E using fixture-backed APIs rather than retailer
   websites.

### F-3: active search path visibility

The API now reports one of:

- `v5_indexed`
- `legacy_indexed`
- `live_fallback`

The value appears in structured startup logs and `/api/health`, together with
the selected relation.

### F-4: SQL identifier safety

Dynamic scheduler and DB-health identifiers now use explicit whitelists and
`psycopg.sql.Identifier`. No request or configuration value is interpolated
into SQL identifiers.

### F-5: production availability plan

Added `docs/PRODUCTION_TOPOLOGY.md` covering:

- managed PostgreSQL and Redis;
- backups, PITR, restore drills, RPO/RTO;
- Redis failover behavior;
- pgbouncer and aggregate connection budgeting;
- threadpool/DB-pool/API-worker sizing;
- staging load validation and required percentile reporting.

The local Compose file remains intentionally scoped to development and
single-node validation.

### F-6: stale frontend-coupled backend test

Removed the test that opened a hard-coded frontend component path. It is now an
OpenAPI contract test for the three public verification endpoints and their
actual response codes.

### F-7: sync route threadpool capacity

Added `MAYABU_API_THREADPOOL_TOKENS`. The API lifespan configures AnyIO's
thread limiter per process and logs the threadpool, Uvicorn-worker, and DB-pool
settings together. `/api/health` exposes the same relationship for operations.

## Additional targeted improvement

Playwright no longer hard-codes `/usr/bin/chromium`. CI and normal developer
machines use Playwright's managed Chromium. A custom executable is used only
when `PLAYWRIGHT_CHROMIUM_PATH` is explicitly set.

## Validation executed

Backend:

- `python -m pip check`: passed
- `python -m compileall -q mayabu mayabu_db mayabu_refresh`: passed
- `ruff check mayabu mayabu_db mayabu_refresh tests`: passed
- `pytest -q`: 42 passed, 1 skipped PostgreSQL integration test
- Docker Compose YAML parse: passed
- GitHub Actions YAML parse: passed

Frontend:

- `npm ci`: passed
- `npm run typecheck`: passed
- `npm run lint`: passed
- `npm run format:check`: passed
- `npm run test`: 29 passed
- `npm run build`: passed for client, SSR server, and ten prerendered routes
- prerender verification: passed
- SEO verification: passed
- `npm audit --omit=dev`: zero vulnerabilities

## Environment-limited checks

- A live PostgreSQL/Redis migration and integration run was not possible in the
  build environment.
- Real Amazon, Flipkart, Croma, and Reliance Digital browser checks were not
  run.
- Playwright browser execution on this host did not finish because its system
  Chromium environment is administrator-restricted. The CI workflow uses
  Playwright-managed Chromium and keeps E2E as a required independent job.
- No production load test was claimed. The staging procedure and existing
  percentile benchmark scripts are documented for the deployment environment.

## Deliberately not added

- Kafka, RabbitMQ, Kubernetes, or a new queue system.
- OpenTelemetry dependencies before there is a deployed collector and an
  operational tracing plan.
- Embedded PostgreSQL/Redis HA inside the local development Compose file.

These would add operational cost without fixing the current audited blockers.
