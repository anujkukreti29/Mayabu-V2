# Mayabu Production Operations Runbook

Concise first-response guide. Metrics: `GET /api/metrics` (admin token when configured). Health: `/api/live`, `/api/ready`, `/api/health`.

## Dependency model

| Process | PostgreSQL | Redis search cache | Redis rate-limit / slots | Retailer sites |
|---------|------------|--------------------|--------------------------|----------------|
| API | **required** (readiness) | optional fail-open | optional; process-local fallback if Redis down | external |
| Scheduler | **required** | optional | optional | does not scrape |
| Worker | **required** | optional | required only when distributed scraper slots enabled | external runtime |

A blocked retailer must **not** make `/api/ready` fail.

---

## API unhealthy / 5xx elevated

1. `/api/live` — process up?
2. `/api/ready` — DB reachable?
3. `/api/health` — `database`, `db_pool`, `oldest_pending_age_seconds`
4. Metrics: `mayabu_http_request_duration_ms`, `mayabu_http_requests_total{status_class="5xx"}`
5. Logs: `request_id` on failing responses

## Database unavailable

1. Expect `/api/ready` → 503; `/api/live` still ok
2. Workers must not mark tasks completed if DB write failed
3. After recovery: confirm pool reconnect via `/api/health.db_pool`

## Redis unavailable

1. Search cache: fail-open (miss path continues)
2. `/api/health` may show `degraded` + `redis=error` — API stays ready
3. If rate-limit relies on Redis: falls back to process-local (limits not shared across workers)

## Worker queue growing / oldest task age high

1. Metrics: `mayabu_queue_pending`, `mayabu_queue_oldest_pending_age_seconds`
2. Admin `/api/health`: `worker_status`, `workers_seen_recently`, `worker_heartbeats`, `pending_tasks`
   - `worker_status=stale|none` → treat as worker outage (API can still be `/ready`)
   - Heartbeat window is ~120s; a just-killed worker may still look “ok” briefly — trust rising `oldest_pending_age_seconds`
3. Dominant cost is often scraper latency, not matching
4. Inspect platform×category empty/blocked rates

### Worker-absent drill (tested locally 2026-09-20)

1. Stop worker process(es)
2. `POST /api/products/{id}/verify-price` → `202 queued`
3. Expect: task `pending`, `oldest_pending_age_seconds` increases; UI must **not** show success
4. Restart supervised worker → task claimed (`running`/`completed`)
5. Alert should fire on oldest-age / worker stale once monitoring is wired (not proven here)

## Scheduler heartbeat stale / automation backlog

1. Admin `/api/health.scheduler`: `scheduler_alive`, `scheduler_functioning`, `heartbeat_age_seconds`, `last_tick_result`, `last_tick_duration_ms`, `last_tick_jobs`
2. `/api/health.automation`: `queue_stalled`, `workers_recent`, `pending_tasks`
3. If `MAYABU_SCHEDULER_ENABLED=true` and heartbeat age > 3 minutes: restart `python -m mayabu.scheduler` (or `mayabu-scheduler.service`)
4. A process that is alive but `last_tick_result=error` is **not** functioning — health is `degraded` (`scheduler_tick_failing`)
5. Scheduler creating jobs with no recent worker heartbeat is `worker_queue_stalled`
6. API and Check latest price keep working; only recurring discovery/refresh stops
7. After restart, pending tasks must not duplicate (`refresh_listing:{listing_id}`, `discovery:{plan_id}`)
8. Backlog: `oldest_pending_age_seconds`, `dead_tasks_24h`, platform scrape_budget remaining
9. Do not raise worker concurrency to "catch up" on a blocked/captcha platform

## Retailer scraper suddenly empty

1. `mayabu_scraper_empty_total{platform,category}`
2. Anomaly events / circuit breaker state
3. Bounded live smoke only — do not load-test retailers
4. Distinguish blocked page vs parser regression vs upstream outage
5. Worker classifies failures as timeout/network/parsing/empty/challenge/login-required/blocked/invalid-price/unavailable/unknown. Parser bugs must not be recorded as retailer blocking.

## Platform blocked

1. Coverage readiness stays `blocked`/`disabled` (config)
2. Temporary circuit open is health, not readiness
3. Do not force-schedule production discovery for blocked cells

## Price extraction drops

1. Compare accepted vs rejected scraper records
2. Invalid price counters / quality gate anomalies
3. Check whether experimental platforms leaked into public offers (should be gated)

## Worker stuck in running

1. Lease expiry → `requeue_stuck_tasks` recovers
2. Metric: long `mayabu_queue_running` with rising oldest age
3. Do not mark complete on crash/lease loss

## High search latency

1. Split metrics: parse / candidates / facets / rank / serialize / cache hit|miss
2. Pool waits: `mayabu_db_acquire_duration_ms`, `mayabu_db_pool_waiting`
3. Stampede: identical misses coalesce via in-process singleflight

## Email provider down

1. Metric: `mayabu_email_send_total{type,result!="ok"}`
2. Accounts remain unverified; resend available
3. Do not delete users because delivery failed
4. Check Resend status / DNS / API key without logging the key

## Bad deployment / migration failure

1. Stop rollout — do not serve new app on failed migration
2. Keep previous API/frontend revision online
3. Inspect migration error; forward-fix preferred
4. Re-run `python -m mayabu_db.migrate --status`

### Live verification write failures

If `live_verification_events.error_code` / task `last_error` contains `IndeterminateDatatype` / `could not determine data type of parameter`:

1. Likely SQL binding of NULL prices without casts (fixed in refresh ingestion `::numeric` CASE)
2. Restart workers so they load the fixed code
3. Pending retries may wait on `scheduled_at` backoff — inspect before extending client poll timeouts

## Auth / session incidents

1. Spike in `mayabu_auth_login_total{result="failure"}` — check rate limits vs attack
2. Session validation failures — Redis outage should **not** log users out (PG authoritative)
3. Cookie Secure/SameSite mismatches after domain change — verify HTTPS + proxy proto

## Check Latest Price backlog / user_verify_stalled

1. `/api/health.automation.user_verify`: pending, oldest age, 24h p50/p95, terminal/partial %
2. `user_verify_stalled` when pending verify > 0, workers stale, oldest ≥ 120s
3. Confirm coalesce/fresh/cooldown still preventing scrape storms
4. Do not raise retailer concurrency to clear backlog during challenge spikes

## Retailer kill switches

1. Disable platform×category via coverage readiness / config (`disabled` / `blocked` cells)
2. Prefer config/env over code rewrite; restart workers after config change
3. Discovery/enrichment/scheduler classes can be paused via `MAYABU_SCHEDULER_*` limits
4. Live verify may be rate-limited / fail-closed when Redis slots unavailable in production

## Suspected wrong prices (bad scraper release)

1. Preserve evidence: sample listing IDs, observation timestamps, raw artifact refs (internal)
2. Disable affected platform×category (kill switch) — stop public promotion of bad offers
3. Do not mass-delete history; quarantine / needs_review as appropriate
4. Revalidate controlled samples against retailer PDP
5. Fix parser; restore cell carefully with small verify batch

## Suspected false OOS spike

1. Inspect stock confidence / reason codes on recent observations
2. Downgrade or disable parser cell if confidence gates fail
3. Prefer preserving prior trusted in-stock values over promoting false OOS
4. Sample live PDPs; restore only after gate passes

## Deployment rollback

1. Prefer rolling back application images **only if** schema remains compatible
2. Destructive migrations require forward-fix or restore-from-backup — never assume code rollback is safe
3. Stop workers/scheduler on bad scrape release before API rollback when prices are wrong
4. Migration failure: halt deploy; keep previous revision; see “Bad deployment / migration failure”

## Retention

See `docs/RETENTION_POLICY.md` for sessions, watch events, scrape_tasks, observations.

---

## Recommended alert signals (initial, tune per env)

| Signal | Starting suggestion |
|--------|---------------------|
| API p95 | > 1500 ms sustained 5m (local multi-worker differs) |
| 5xx rate | > 1% of requests / 5m |
| Ready failures | any sustained |
| Oldest pending age | > 30–60 min for production queues |
| Scraper empty rate | spike vs 24h baseline per production platform×category |
| DB acquire timeouts | > 0 sustained |
| Search cache errors | spike (degraded, not outage) |
| Matching relation mix | sudden huge shift in exact/conflict ratio |
| Email send failures | spike in `mayabu_email_send_total{result=~"timeout|error|rejected"}` |
| Auth login failures | unusual burst vs baseline (after excluding rate-limit 429) |

Provisional engineering thresholds only — not an SLA.

---

## Release smoke

```bash
python scripts/release_smoke.py --base-url https://staging.example --frontend-url https://staging.example --admin-token "%MAYABU_ADMIN_TOKEN%"
```

---

## Capacity commands

```bash
# Capacity matrix (rate-limit OFF for backend capacity)
set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test
python scripts/ops_capacity_matrix.py --workers 1,2,4 --concurrency 10,25,50,100 --rate-limit off

# Real behavior with rate limit ON (429 expected under burst)
python scripts/ops_capacity_matrix.py --workers 2 --concurrency 50,100 --rate-limit on

# Existing helpers
python scripts/hardening_api_load_test.py --concurrency 25 --requests 100
python scripts/hardening_write_load_test.py --workers 8 --iterations 20
python scripts/benchmark_matching_scale.py
python scripts/audit_product_matching.py --dry-run
```
