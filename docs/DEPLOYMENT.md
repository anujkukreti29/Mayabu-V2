# Mayabu deployment

## Local development

```cmd
docker compose up -d postgres redis
python -m mayabu_db.migrate
python run_api.py
```

## Worker and scheduler commands

```cmd
python -m mayabu.scheduler.task_materializer refresh --limit 50
python worker_db.py --once
python worker_db.py --loop --concurrency 2
```

## Production boundary

The root `docker-compose.yml` is for local and single-node validation. For
production, use managed PostgreSQL and Redis on private networking, automated
backups, HTTPS, explicit CORS origins, and separate API and worker services.

Mayabu v5.3 shares one Redis-backed per-platform scraper budget across discovery,
refresh, direct ingestion, and live verification. Multiple worker replicas are
safe only while Redis coordination is healthy; production workers fail closed
if the distributed gate is unavailable.

Read `docs/PRODUCTION_TOPOLOGY.md` before increasing API or worker replicas. It
documents PostgreSQL/Redis availability, pgbouncer, connection budgeting,
threadpool tuning, restore drills, and staging load validation.
