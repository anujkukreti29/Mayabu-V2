# Mayabu v5.2 Live Price Verification

Mayabu returns stored PostgreSQL prices immediately. A user can click **Verify current price** to queue a bounded check of a known product-detail URL. Public API requests never run a scraper inline.

## Scale and safety

- One active task per stable platform-listing UUID.
- A two-second Redis response cache absorbs same-product click bursts.
- PostgreSQL idempotency remains the durable fallback if Redis is unavailable.
- Recent Redis/DB results are reused without creating tasks.
- Per-client and global request limits protect the API and DB pool.
- The active verification queue has a hard PostgreSQL cap.
- Best-offer mode queues one listing; all-offer mode is capped.
- Workers use local semaphores and Redis cross-process platform slots.
- Production fails closed when the distributed platform gate is unavailable.
- Lightweight structured HTML is tried first; Playwright is only the fallback.
- Circuit breakers, retries, cooldowns, leases, and anomaly logging remain active.
- User IPs and browser networks are never used as scraper proxies.

## 1,000 different products

Mayabu does not launch 1,000 browsers. It admits requests at a configurable global rate, stores accepted work in the durable queue, and runs only the configured number of workers/platform slots. Excess requests get an immediate busy response while the last known price stays visible.

Recommended starting values:

```env
MAYABU_LIVE_VERIFY_GLOBAL_PER_MINUTE=300
MAYABU_LIVE_VERIFY_QUEUE_MAX_ACTIVE=2000
MAYABU_WORKER_CONCURRENCY=2
MAYABU_SCRAPER_PLATFORM_CONCURRENCY=2
```

Increase these only after staging load tests and platform-health measurements.

## Public endpoints

```text
POST /api/products/{product_id}/verify-price
GET  /api/verification-jobs/{task_id}
GET  /api/products/{product_id}/verification-status
```

Request:

```json
{"mode":"best_offer"}
```

Use `all_offers` only when the user explicitly asks to refresh every known offer.

## Freshness states

- `fresh`: recent result returned; no task created.
- `queued`: new durable task created.
- `joined`: active task shared with another request.
- `cooldown`: recent attempt or failure prevents another request.
- `busy`: queue or global admission capacity reached.

The UI always keeps the last known price visible.

## Proxy-header safety

`X-Forwarded-For` is ignored by default. Enable `MAYABU_TRUST_PROXY_HEADERS=true` only when a trusted load balancer or reverse proxy removes client-supplied forwarding headers and writes its own.
