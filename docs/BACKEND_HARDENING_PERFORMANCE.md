# Mayabu Backend Hot Paths & Performance Budgets

Practical reference for production hardening. Not an SLA.

## Main request path (public API)

1. FastAPI route validates query bounds.
2. Optional Redis `search:v6:*` cache lookup (fail-open if Redis down).
3. Query parse → category inference → PostgreSQL search documents.
4. Ranker (query tokens prepared once per page).
5. Query-scoped facets from the same candidate sample.
6. Compact serialization.

## Search hot path

- Source: `product_search_documents` (+ best-price fields refreshed with public-offer gate).
- Public offers / best price exclude experimental & disabled platform×category cells via `mayabu_listing_is_public_offer`.
- Cache key includes contract version `v6`, category, filters, sort, pagination.
- Redis is **optional cache**; queue coordination may still require Redis in production.

### Local observed budgets (staging hardware, not production promises)

| Path | Median | P95 | Notes |
|------|--------|-----|-------|
| In-process search (mixed categories) | ~6 ms | ~45 ms | Cold p95 includes first-hit pool/index warm-up |
| Synthetic matching 1k–50k | ~2–2.5 ms | ~3–6 ms | Candidate max ≤13 |
| Task claim (`FOR UPDATE SKIP LOCKED`) | sub-ms | — | Exclusive under concurrency tests |

## Ingestion hot path

scraper → quality gate → normalize → match → listing upsert → price observation → daily rollup → search document refresh.

- One transaction per listing (not per crawl).
- Search cache is not globally flushed per discovery batch.

## Matching hot path

category → brand → model fast path → bounded family/text candidates → hard conflicts → classify.

Safety target: **false exact merges = 0**.

Hardening notes:

- CPU series-only evidence is compatible with a more specific same-prefix model (`intel_core_i:5` ≈ `intel_core_i:5:13420h`).
- Discrete GPU differences remain hard conflicts.
- Weak chassis codes (e.g. `15IRX9`) are not strong exact identity alone.
- Washer/dryer dual capacity (`13-10 kg`, `13 kg/10 kg`) uses wash capacity first.

## Worker path

enqueue (idempotent) → claim (`SKIP LOCKED`) → lease → execute → complete/fail/retry/dead.

Permanent parse/blocked failures should not retry endlessly; lease reaper recovers crashed workers.

## DB pool

Process-wide `psycopg_pool.ConnectionPool` (`mayabu_db.connection`).

- Configurable min/max/timeout/lifetime.
- Connections returned via context manager; close scripts with `close_connection_pool(timeout=…)`.

## Repeatable benchmarks

```bash
python scripts/benchmark_matching_scale.py
python scripts/benchmark_search.py --base-url http://127.0.0.1:8000
python scripts/ops_capacity_matrix.py --workers 1,2,4 --concurrency 10,25,50,100 --rate-limit off
python scripts/hardening_api_load_test.py --concurrency 25 --requests 100
python scripts/hardening_write_load_test.py --workers 8 --iterations 20
python scripts/hardening_worker_ingest_promoted.py --dry-run
python scripts/audit_product_matching.py --dry-run
```

Prefer `ops_capacity_matrix.py` for multi-worker capacity; keep `hardening_api_load_test.py` for quick single-target checks.


## Known intentional non-changes

- Candidate count already bounded (~median 13 / p95 24 on real PG); not shrunk for vanity.
- No Kafka/Celery/Elasticsearch introduction.
- Vijay Sales TWS/headphones and Poorvika non-laptop/phone stay experimental.
