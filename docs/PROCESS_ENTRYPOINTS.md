# Mayabu process entrypoints (authoritative)

Use these commands for staging/production. Do not invent a parallel stack.

| Role | Command | Notes |
|---|---|---|
| Migration job | `python -m mayabu_db.migrate` then `python -m mayabu_db.migrate --status` | Run **once** before API/worker rollout |
| API | `python run_api.py` or `uvicorn mayabu.api.main:app --host 0.0.0.0 --port 8000 --workers N` | No `--reload` in staging/prod |
| Frontend (prod) | `cd frontend && npm run build && npm run start` | **Not** `npm run dev` |
| Worker | `python worker_db.py --loop --concurrency 1` (start conservative) | Compose/systemd: `deploy/mayabu-worker.service` |
| Scheduler | `python -m mayabu.scheduler` | Exactly one lease leader; extras standby. `deploy/mayabu-scheduler.service` |
| Maintenance | `python run_maintenance_scheduler.py` | Retention/cleanup; dry-run first |
| Staging doctor | `python scripts/staging_doctor.py --base-url https://…` | Non-destructive |
| Synthetic alert | `python scripts/send_staging_alert.py` | Requires `MAYABU_ALERT_WEBHOOK_URL` |

Compose profiles (`docker-compose.yml`): `app`, `worker`, `scheduler`, `maintenance`.

## Connection budget (staging start)

```
budget ≈ (API_replicas × API_workers × MAYABU_DB_POOL_MAX_SIZE)
       + (worker_replicas × MAYABU_DB_POOL_MAX_SIZE)
       + (scheduler_replicas × pool)
       + admin/migrate headroom (e.g. 5–10)
```

Example (1 API×2 workers×8 pool + 1 worker×8 + 2 schedulers×2 + 10) ≈ 48.
Must stay below managed PG `max_connections` with ≥20% margin.

## Chromium sandbox

- Worker image runs as non-root `mayabu` (uid 10001).
- Default app config: sandbox **on** (`MAYABU_SCRAPER_CHROMIUM_NO_SANDBOX=0`).
- Compose default: `MAYABU_SCRAPER_CHROMIUM_NO_SANDBOX=1` because typical Docker lacks user namespaces for Chromium sandbox as non-root.
- Decision for a host: try sandbox first; only then document **NO_SANDBOX REQUIRED BY HOST** with compensating container isolation.
