# Mayabu v4.2 hardening report

This patch continues from v4.1 and applies the remaining MVP-readiness fixes requested after the v4.1 audit.

## Implemented

1. Amazon `clean_amazon_link()` now iteratively decodes nested `/sspa/click?` and `url=` redirect values and canonicalizes valid ASIN links to `https://www.amazon.in/dp/<ASIN>`.
2. Search now uses hybrid matching: `product_clusters.search_tsv` full-text search, ILIKE/trigram-friendly fallback terms, listing-title fallback, and Mayabu's structured laptop ranker.
3. `daily_product_prices` normal ingest path is incremental per product/day. Full historical rebuild is preserved as `rebuild_daily_product_prices()` and exposed through `python -m mayabu.scheduler.maintenance rebuild-price-rollups`.
4. Public search rate limiting now uses Redis sorted-set sliding windows when Redis is enabled, with in-process memory fallback for local development.
5. `worker_db.py` now has `run_once_async()` and an async worker loop. The old `run_once()` remains as a compatibility wrapper.
6. Docker Compose now includes a profile-gated `worker` service with CPU/memory limits, `shm_size`, and artifact/log mounts. A `Dockerfile.worker` and `.dockerignore` were added.
7. `DEFAULT_USER_AGENT` is now env-configurable and the default was updated from Chrome 124 to a modern Chrome 150-style UA string. No stealth or webdriver-suppression logic was added.
8. Seller-name extraction remains deferred intentionally until search and refresh flows are validated with real data.

## Validation performed in this environment

- `python -m compileall -q .`
- `python tests/smoke_backend.py`

Live PostgreSQL, Redis, Playwright browser execution, and real ecommerce pages still need local validation.
