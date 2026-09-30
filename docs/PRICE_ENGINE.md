# Mayabu Price Intelligence Engine V1

Automated product-price intelligence on the existing PostgreSQL queue. No Celery, Kafka, or RabbitMQ.

## Process topology

| Process | Command | Role |
|---------|---------|------|
| Frontend | `cd frontend && npm run dev` | UI |
| API | `python run_api.py` | Public/read APIs, Check latest price enqueue |
| Scheduler | `python -m mayabu.scheduler` | Recurring discovery + refresh enqueue |
| Worker | `python worker_db.py --loop --concurrency 2` | Retailer I/O, ingest, matching |
| PostgreSQL | required | Queue, listings, history, scheduler lease |
| Redis | optional fail-open | Cache / rate-limit / scraper slots |

Scheduler correctness is **database-backed**. Redis restart does not duplicate or drop scheduling.

## Enablement

Development: `MAYABU_SCHEDULER_ENABLED=false` (default). Local `npm run dev` must not generate unexpected retailer traffic.

Tests: scheduler stays off unless a test enables it, and tests never contact live retailers.

Staging/production: set `MAYABU_SCHEDULER_ENABLED=true` deliberately. Do not treat localhost success as production-ready.

## Leader lock

Leadership is a PostgreSQL session advisory lock (`pg_try_advisory_lock(942001, hashtext(domain))`) held on a **dedicated non-pooled connection**. A heartbeat row in `scheduler_heartbeats` records:

- last tick time
- last successful tick
- last tick duration (`last_tick_duration_ms`)
- jobs created on the last tick
- last error / result
- heartbeat age

A second scheduler process fails `pg_try_advisory_lock` and stays standby — it does not enqueue recurring jobs. If the leader process dies, the lock session disconnects and another instance can acquire immediately. Heartbeat TTL is a health signal, not the correctness source.

Restart resumes from due listings / due plans. Idempotency keys prevent duplicate pending work:

- `refresh_listing:{platform_listing_id}`
- `discovery:{scheduler_plan_id}`

Graceful shutdown: SIGINT/SIGTERM stops the tick loop and releases the advisory lock.

## Tick

Default interval: `MAYABU_SCHEDULER_TICK_SECONDS=60` (lease should exceed tick; default lease 90s).

Each tick (lock holder only):

1. Reap stuck worker leases
2. Materialize due listing refreshes (HOT/NORMAL/COLD, platform fairness, budgets)
3. Materialize due discovery plans (production pairs only)
4. Bounded demand-cluster discovery
5. Drain dirty search documents
6. Write heartbeat (including tick duration)

If the scheduler dies: API stays up, workers finish queued work, Check latest price still enqueues, **recurring** refresh stops until restart.

## Refresh tiers

Aggregate signals only (wishlist counts, `product_activity_hourly`). No personal profiling.

| Tier | Default cadence | Queue priority | When |
|------|-----------------|----------------|------|
| HOT | 180 minutes (`MAYABU_REFRESH_HOT_MINUTES`) | 40 | Wishlisted, recent activity, or price changed in 7 days |
| NORMAL | 720 minutes | 80 | Everything else that is still moving |
| COLD | 1440 minutes | 120 | No wishlist, no 7-day activity, no price change in 30 days |

User Check latest price remains priority 5 and may **promote** a pending `refresh_listing` for the same listing URL. Frontend must never claim success merely because a task was queued.

## Discovery

Uses existing `scheduler_plans` cadence + `last_materialized_at`. Incremental page cursors live in `scheduler_plans.metadata.cursor.last_page` (PostgreSQL, survives restart). Amazon, Flipkart, Reliance Digital, and Poorvika search pagination accept `start_page`. Rotation wraps at page 8.

**Limitations:** Croma discovery is click-budget based, not page-offset. Poorvika category landings use PIM JSON, not a search page cursor. Those adapters keep bounded restart discovery; the cursor is recorded as `bounded_restart` rather than faked incrementality.

URL identity is `platform_listings (platform, listing_url_hash)`. Repeated rediscovery does not create a second logical listing.

Production pairs only (`public_offer_allowed` / coverage). JioMart stays disabled. Bajaj Electronics stays blocked. No CAPTCHA bypass.

Ambiguous listings stay `unmatched` / `needs_review`. False exact merge is worse than unmatched.

## Matching

Existing identity engine is unchanged in philosophy. Internal match evidence includes an `explanation` and hard-conflict reasons. Consumer UI must not show raw match scores or confidence percentages.

Uncertain listings are quarantined (`needs_review` / unmatched), not force-merged. New canonical products are created only when identity quality is adequate.

Curated golden-set metrics apply **only** to that benchmark. They are not marketplace accuracy.

## History

`daily_product_prices` + `daily_product_platform_prices` remain source of truth.

`GET /api/products/{id}/price-history?window=30d|90d|180d|1y|all` returns `best_price` series, `platforms` map, and backward-compatible `history`. Missing days are unobserved — never interpolated in the API. Frontend may draw lines but gaps stay semantically unobserved.

OOS last-known retained prices must not masquerade as a newly observed in-stock price. Public best price: in-stock public priced offers win; only when none exist may an eligible OOS last-known price be a fallback.

## Price timing (Price Intelligence)

`GET /api/products/{id}/price-intelligence`

One shared deterministic backend service. PDP, and later Search/Compare, must consume this contract rather than recomputing.

Public states:

| State | Meaning |
|-------|---------|
| `CONSIDER_NOW` | Fresh in-stock price is within 3% of the 90-day/tracked low, **at least two in-stock public stores**, enough history. Single-store products stay `WATCH` with `SINGLE_STORE` (confidence rule, not an accident). |
| `WATCH` | Mixed evidence, recent drop still above the low, stale, or single-store |
| `WAIT_FOR_BETTER_PRICE` | Current price is ≥8% above the recent low. Not a forecast. |
| `INSUFFICIENT_HISTORY` | Fewer than configured observation/tracking days |
| `UNAVAILABLE` | No priced public offers, or OOS-only last-known fallback |

OOS-only last-known fallback **cannot** produce `CONSIDER_NOW`. Stale offers (older than `MAYABU_INTELLIGENCE_STALE_HOURS`, default 24) cannot produce `CONSIDER_NOW`.

Every signal includes machine-readable `reason_codes` and a consumer-readable factual explanation derived from computed numbers. This is **not** a price forecast. Mayabu does not predict future retailer prices.

Minimum history defaults: `MAYABU_INTELLIGENCE_MIN_OBSERVATION_DAYS=7`, `MAYABU_INTELLIGENCE_MIN_TRACKING_DAYS=14`.

## Price Watch

Wishlist columns: `target_price`, `notify_on_drop`. `PATCH /api/wishlist/{product_id}` stores intent. **Email delivery is deferred** until Resend staging proof.

## Observability

Health (`/api/health`, admin on deployed environments) includes scheduler heartbeat, catalog freshness (1h/6h/24h/stale, by platform×category), retailer health, unmatched/review counts, and queue oldest age.

Metrics (bounded labels only — never product ID, URL, title, user ID, or listing ID):

- `mayabu_scheduler_tick_total{result}`
- `mayabu_scheduler_tasks_created_total{task_type}`
- `mayabu_scheduler_heartbeat_age_seconds`
- `mayabu_price_signal_total{signal}`
- `mayabu_discovery_total{platform,category,result}`
- `mayabu_matching_results_total{category,relation}` (match decisions)
- `mayabu_queue_oldest_pending_age_seconds`
- existing scraper/refresh/worker counters

## Failure / backoff

Platform health + scrape budgets reduce pressure. Worker `fail_task` uses bounded exponential backoff. CAPTCHA/block is recorded as operational state, not circumvented. One retailer/category failure does not stop the tick loop.

## Cache

Successful **material** price changes invalidate product, price-history, and price-intelligence keys plus that product's search document, and drop the homepage snapshot. Unchanged refresh still rebuilds the product search document and drops product/history/intelligence keys so "checked ago" can update; it does **not** drop the homepage snapshot. Never flush all Redis.

Unmatched / `needs_review` listings are refreshed for rematch evidence. They never contribute to public best price, Search, or Price Intelligence (`match_status='matched'` is required).

`daily_product_prices` remains price-only. Listing-day `in_stock_observations` may be attached when `daily_listing_prices.in_stock_count` exists. A historical price does **not** imply the product was in stock that day.

Auto-circuit `blocked` + `circuit_open_until` in the past is treated as cooldown elapsed: refresh may retry. Sticky `blocked` with no cooldown timestamp still skips work.

## Local commands

```bash
python -m mayabu_db.migrate
python run_api.py
python -m mayabu.scheduler
python worker_db.py --loop --concurrency 2
cd frontend && npm run dev
python scripts/dev_doctor.py
```

Live smoke (manual, bounded, production pairs only):

```bash
python scripts/price_engine_smoke.py --help
python scripts/price_engine_smoke.py --local
python scripts/price_engine_smoke.py --live --confirm MAYABU_LIVE_SMOKE=1 --limit 2
```

`--live` still monkeypatches due candidates to the selected sample so the catalog scheduler is not enabled. Tests never hit live retailers.

Duplicate URL-hash audit (report only, no deletes): `python scripts/audit_listing_url_duplicates.py`

## Runtime proof notes

Controlled live smoke is **not** a production rollout. It demonstrated scheduler-created `refresh_listing` tasks (`created_by=scheduler`, `metadata.task_source=scheduler_refresh`) leased by the worker, hitting Amazon PDP adapters, persisting observations, and updating last-known prices/stock.

- Development remains `MAYABU_SCHEDULER_ENABLED=false` by default.
- Live smoke requires `--live --confirm MAYABU_LIVE_SMOKE=1`.
- Scheduled refresh accepts a successful explicit `out_of_stock` page even when price is null, keeps last-known `current_price`, and records observation stock. `CONSIDER_NOW` stays forbidden on OOS-only products.
- `daily_product_platform_prices` is created if missing; ingest uses savepoints so a missing rollup table cannot abort the observation transaction.
- `evaluate_watches` savepoints around `user_wishlist` so a missing wishlist table cannot abort a price-drop ingest.
- Public SQL `current_product_best_prices` must include the OOS last-known fallback (`mayabu_listing_is_public_priced`). Incomplete catalogs with the older in-stock-only view show null PDP/Search best prices while Python `compute_public_best_price` still falls back — apply `mayabu_db/migrations/2026_09_21_public_best_price_oos_functions.sql`.
- Intelligence `current.price` is null on OOS-only products; public best-price may still expose labeled last-known fallback. That split is intentional.
- Croma / Poorvika discovery remain `bounded_restart` (no true page cursor).
- Matching golden set is curated-benchmark only. Zero false exact merges on that set is not marketplace accuracy.
- URL-hash UNIQUE remains deferred. A small local catalog may have 0 duplicate groups; do not assume other environments are clean.

## Launch

This engine can be locally correct and still **production NO-GO** until external staging (HTTPS, Resend, managed PostgreSQL/Redis with TLS, backups, monitoring) is proven. Localhost tests do not mark those blockers PASS.
