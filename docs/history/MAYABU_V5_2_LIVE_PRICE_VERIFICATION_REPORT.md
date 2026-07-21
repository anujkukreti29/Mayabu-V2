# Mayabu v5.2 — Efficient Live Price Verification

## Build objective

Add a useful **Verify current price** feature without turning public product pages into unbounded scrape-on-demand infrastructure.

## Implemented

- Cached PostgreSQL prices remain visible immediately; the API never waits for a scraper.
- Best-offer verification by default; explicit all-offer mode is capped at four listings.
- Two-second Redis request coalescing reduces same-product API/DB bursts before durable queue idempotency takes over.
- One active durable task per stable platform-listing UUID, even if product clusters are later merged or reassigned.
- Duplicate users join the same task and increment `request_count` instead of creating more scrapers.
- Per-client and configurable global verification admission limits smooth many-different-product bursts.
- Atomic PostgreSQL active-queue cap, priorities, leases, retries, dead tasks, and circuit breakers.
- Process-local platform semaphores plus Redis cross-process slots; production fails closed if the distributed gate is unavailable.
- Short slot wait and deferred retry avoid wasting worker capacity; slot TTL covers configured browser retries/timeouts.
- Per-listing freshness, cooldown, exponential failure backoff, status, source, and timestamps.
- Lightweight JSON-LD/meta verification before Playwright fallback.
- Cross-domain redirect validation, bounded 2 MB HTML reads, and explicit captcha/block handling.
- Out-of-stock verification can succeed without deleting the last known price.
- Product-scoped cache invalidation only; the search cache is not wiped after each price update.
- Public job polling and product verification-status endpoints.
- Anonymous browser client ID improves rate-limit fairness behind shared networks; user networks are never used as proxies.
- Proxy forwarding headers are ignored unless `MAYABU_TRUST_PROXY_HEADERS=true` is explicitly enabled behind a trusted reverse proxy.
- Nightly retention removes old verification events to keep storage bounded.
- Admin metrics expose queue depth, coalesced demand, success/failure, and average duration.

## Behavior under load

### Many users, same product

A short Redis response cache absorbs the immediate burst, then PostgreSQL idempotency guarantees one active task per listing.

```text
1,000 clicks for one listing -> one durable verification task
```

### Many users, different products

Requests are smoothed before they can exhaust the DB pool, admitted into a bounded durable queue, and processed by a small controlled worker pool.

```text
1,000 different products
-> per-client + global admission guard
-> active queue cap
-> bounded workers
-> strict per-platform concurrency
-> cached prices remain visible for delayed/rejected requests
```

## Public endpoints

```text
POST /api/products/{product_id}/verify-price
GET  /api/verification-jobs/{task_id}
GET  /api/products/{product_id}/verification-status
```

## Validation completed in the build environment

- Ruff passed.
- Python compilation passed.
- 35 tests passed; one PostgreSQL integration test remains skipped without a live DB.
- Existing backend smoke and matching sanity scripts passed.
- PostgreSQL schema parsed successfully with `pglast` (199 statements).
- FastAPI OpenAPI generated as v5.2.0 with 27 paths.

## Not live-verified in the build environment

- Migration against the user’s existing PostgreSQL data.
- Redis behavior across multiple real machines/containers under failure.
- Live Amazon/Flipkart/Croma/Reliance responses and anti-bot behavior.
- Browser fallback under real platform blocks.
- Frontend production build because npm dependencies were unavailable in the artifact environment.
- Realistic sustained load and capacity limits.

Run the included verification, integration, and benchmark scripts locally before deployment.
