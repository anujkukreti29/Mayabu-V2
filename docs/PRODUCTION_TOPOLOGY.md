# Mayabu production topology and availability plan

This document defines the infrastructure boundary for Mayabu v5.3. The local
Docker Compose file remains a development and single-node validation setup. It
is not an HA deployment template.

## Recommended stages

### Stage 1: controlled MVP

- One API host with 1-2 Uvicorn worker processes.
- One background worker replica with concurrency 1-2.
- One scheduler replica (`python -m mayabu.scheduler`) with a database lease; extra replicas standby.
- Managed PostgreSQL with automated backups and point-in-time recovery.
- Managed Redis with persistence disabled for cache data but an HA/failover
  option enabled because Redis also coordinates rate limits and scraper slots.
- HTTPS reverse proxy and private service networking.

### Stage 2: horizontal application scale

Before adding worker replicas:

1. Keep `MAYABU_SCRAPER_PLATFORM_CONCURRENCY` conservative. It is now enforced
   across all replicas by the shared Redis lease in v5.3.
2. Require Redis availability in production. Workers fail closed when the
   distributed platform gate cannot be reached.
3. Put PostgreSQL behind a transaction-aware connection pooler such as
   pgbouncer when aggregate process pools approach the database connection
   budget.
4. Calculate the maximum possible application connections as:

   `API replicas * API workers * DB pool max + worker replicas * DB pool max`

5. Leave headroom for migrations, maintenance, monitoring, and emergency access.

## PostgreSQL requirements

- Automated encrypted backups.
- Point-in-time recovery.
- Regular restore drills.
- A standby/read replica or managed multi-zone failover before a public uptime
  commitment.
- Connection alarms and slow-query monitoring.
- `EXPLAIN (ANALYZE, BUFFERS)` review for the search and product-detail hot paths.

Suggested initial targets:

- Recovery point objective: 15 minutes or better.
- Recovery time objective: 60 minutes or better.
- Alert at 70% and 85% of the configured connection ceiling.

## Redis requirements

Redis is not the system of record, but it coordinates cache, rate limiting,
request coalescing, and cross-process scraper capacity. Production should use a
managed primary/replica or Sentinel/cluster arrangement with automatic failover.

During a Redis outage:

- Normal reads can continue from PostgreSQL where supported.
- Cache efficiency degrades.
- Production verification admission and distributed scraper capacity fail
  closed to prevent unbounded retailer traffic.

## API threadpool and DB pool relationship

FastAPI sync handlers execute in AnyIO's bounded threadpool. Configure:

- `MAYABU_API_WORKERS`: operating-system processes.
- `MAYABU_API_THREADPOOL_TOKENS`: concurrent sync handlers per process.
- `MAYABU_DB_POOL_MAX_SIZE`: PostgreSQL connections per process.

A larger threadpool does not create more database capacity. Start with 40
thread tokens and 10 DB connections per process, observe pool waiting, then tune
from measurements rather than increasing both blindly.

## Required staging validation

Run these against a restored staging database and non-production retailer test
traffic before increasing replicas:

```cmd
python -m mayabu_db.migrate
python scripts\verify_v52.py
python scripts\benchmark_search.py --requests 1000 --concurrency 25
python scripts\benchmark_verification.py --product-ids staging_product_ids.txt --requests 100 --concurrency 10
```

Record p50, p95, p99, error rate, DB-pool waiting, Redis failures, queue depth,
and per-platform scraper concurrency. Do not use production scale settings until
these numbers are reviewed.
