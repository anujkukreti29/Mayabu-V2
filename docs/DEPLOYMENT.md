# Mayabu Deployment

## Environments

| Env           | Purpose     | Indexing                     | Email                | Cookies Secure   | Localhost URLs                                   |
| ------------- | ----------- | ---------------------------- | -------------------- | ---------------- | ------------------------------------------------ |
| `development` | local FE/BE | intended robots for local QA | console/dev inbox OK | optional         | allowed                                          |
| `test`        | pytest      | n/a                          | console              | optional         | allowed                                          |
| `staging`     | pre-prod    | **noindex**                  | Resend preferred     | yes behind HTTPS | forbidden unless `MAYABU_ALLOW_INSECURE_LOCAL=1` |
| `production`  | live        | indexable                    | **Resend required**  | required         | **forbidden**                                    |

Templates:

- `.env.example` — local development
- `.env.staging.example`
- `.env.production.example`

Never put DB/Redis/email secrets in `VITE_*`.

## Preferred public topology

One public origin via reverse proxy:

```
https://mayabu.example/          → frontend (SSR)
https://mayabu.example/api/*     → FastAPI
```

Benefits: host-only cookies, simpler CSRF/CORS, browser `same-origin` API mode.

Trusted proxy boundary: only the reverse proxy may set `X-Forwarded-Proto` / `X-Forwarded-For`.
Set `MAYABU_TRUST_PROXY_HEADERS=true` **only** when the app is not reachable directly from the internet.

HTTP→HTTPS redirect and www↔apex redirect belong at the edge (not in-app loops).

## First deploy procedure

1. Provision managed PostgreSQL (TLS/`sslmode=require` as required by provider).
2. Provision managed Redis (`rediss://` when required).
3. Load secrets from a secret manager (not baked into images).
4. Configure Resend + verified sending domain + `MAYABU_AUTH_PUBLIC_BASE_URL=https://…`.
5. Run migrations **before** switching traffic:
   ```bash
   python -m mayabu_db.migrate
   python -m mayabu_db.migrate --status
   ```
6. Deploy API (no `--reload`):
   ```bash
   MAYABU_ENV=production python run_api.py
   # or: uvicorn mayabu.api.main:app --host 0.0.0.0 --port 8000 --workers 2
   ```
7. Deploy workers as a **supervised permanent service** (not a manual terminal):
   ```bash
   # Docker Compose (local/staging-like)
   docker compose --profile worker up -d worker

   # systemd (example unit checked in)
   sudo cp deploy/mayabu-worker.service /etc/systemd/system/
   sudo systemctl enable --now mayabu-worker
   ```
   Requirements: automatic start, restart-on-failure, graceful SIGTERM, journal/structured logs.
   Confirm `/api/health` (admin) shows `worker_status=ok` and `workers_seen_recently >= 1`.
7b. Deploy the **scheduler** independently (optional until automation is explicitly enabled):
   ```bash
   sudo cp deploy/mayabu-scheduler.service /etc/systemd/system/
   sudo systemctl enable --now mayabu-scheduler
   ```
   Set `MAYABU_SCHEDULER_ENABLED=true` only after workers and coverage are green.
   Confirm `/api/health` (admin) `scheduler.scheduler_alive=true`.
8. Build/run frontend production artifact (`npm run build` && `npm run start`). Do **not** use Vite `dev` as staging proof.
9. Configure reverse proxy / CDN (do not CDN-cache account/wishlist/auth HTML). Example: `docs/nginx.mayabu.example.conf`.
10. Smoke + doctor:
    ```bash
    python scripts/release_smoke.py --base-url https://staging.example --frontend-url https://staging.example --admin-token "$MAYABU_ADMIN_TOKEN" --product-id <uuid>
    python scripts/staging_doctor.py --base-url https://staging.example --admin-token "$MAYABU_ADMIN_TOKEN"
    ```
11. Enable scheduler only after readiness is green.
12. Verify robots/sitemap/canonicals — staging must remain noindex; do not submit staging sitemaps.
13. Observe metrics (admin-protected) and logs. Wire scraper/queue/worker panels before calling alerts “ready”.

### Staging lessons (2026-09-20 local proof run)

- Workspace had **no** real staging hostname, Resend key, or managed PG/Redis → those gates stay **BLOCKED / MANUAL EXTERNAL**.
- Local Docker `pg_dump`/`pg_restore` works when host PATH lacks clients: `docker exec <postgres> pg_dump …`.
- Application DB in this workspace was `mayabu_test` on `127.0.0.1:5433` — always dump the DB the API actually uses.
- TWS verify-price failure was **not** a poll-timeout: NULL `current_price` in SQL `CASE %s IS NOT NULL` raised `IndeterminateDatatype` ($11). Fixed with `::numeric` casts in `mayabu_db/refresh_ingestion.py`.
- Worker must be restarted after code fixes; failed tasks may sit behind `scheduled_at` backoff before reclaim.

## Connection budget

Starting point (tunable):

- `MAYABU_API_WORKERS=2`
- `MAYABU_DB_POOL_MAX_SIZE=8` → ~16 API connections
- plus worker pools + migration/admin sessions

Must stay under managed Postgres `max_connections`.

## Migrations

Ledger table: `schema_migrations(version, applied_at, checksum)`.

```bash
python -m mayabu_db.migrate            # baseline schema.sql + pending migrations/
python -m mayabu_db.migrate --dry-run
python -m mayabu_db.migrate --status
```

If a migration fails, the deploy stops. Do not start the new app version on a partial schema.
Prefer forward-fix migrations; avoid destructive rollbacks.

## Rollback

1. Keep previous frontend/API images/builds.
2. Roll traffic back to previous app revision.
3. DB: prefer forward fix; do not drop columns/tables on rollback unless rehearsed.
4. Invalidate CDN HTML if mis-cached (should be `private, no-store` for auth SSR).

## Containers

- `Dockerfile.api`, `Dockerfile.worker`, `frontend/Dockerfile` — non-root users, no `.env` baked in.
- Root `docker-compose.yml` is for local/single-node validation (`profiles: app`), not managed production.

## Health

| Path           | Public?                | Meaning             |
| -------------- | ---------------------- | ------------------- |
| `/api/live`    | yes                    | process up          |
| `/api/ready`   | yes                    | PostgreSQL required |
| `/api/health`  | admin in staging/prod  | detailed ops        |
| `/api/metrics` | admin / network policy | Prometheus          |

## Related docs

- `docs/BACKUP_RESTORE.md`
- `docs/PRODUCTION_SECURITY.md`
- `docs/LAUNCH_CHECKLIST.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/PRODUCTION_TOPOLOGY.md`
- `docs/ACCOUNT_SYSTEM.md` (email)
