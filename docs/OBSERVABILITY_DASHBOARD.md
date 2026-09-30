# Mayabu Observability Dashboard Spec

No Grafana provisioning is present in-repo. Use this layout with Prometheus scrapes of `GET /api/metrics` (protect with admin token / network policy in production).

## API

- RPS: `rate(mayabu_http_requests_total[1m])`
- Latency p50/p95/p99: histogram `mayabu_http_request_duration_ms`
- 5xx / 429 rates by `status_class`
- In-flight: `mayabu_http_in_flight`

## Search

- Total p95: `mayabu_search_duration_ms`
- Stages: parse / candidate / facet / rank / serialize histograms
- Cache: `mayabu_search_cache_events_total{event=hit|miss|error}`
- Candidate/result counts histograms by `category`, `search_mode`

## Database

- Pool size / in-use / waiting gauges
- Acquire latency histogram
- Acquire errors counter
- Logical ops (when instrumented): `mayabu_db_operation_duration_ms{operation=...}`

## Queue / Workers

- Pending / running gauges
- Oldest pending age (seconds)
- Claim latency
- Task outcomes: `mayabu_worker_tasks_total{task_type,platform,result}`
- Task duration histogram

## Scrapers / Prices

- Discovery duration by platform/category
- Empty scrape counter
- Record accepted/rejected
- Price observation outcomes

## Health overlays

- Ready/unready from blackbox or `/api/ready`
- Degraded redis from `/api/health` (not a page failure) — protect detailed health with admin token in staging/prod
- Platform×category readiness counts from health JSON (config), separate from temporary circuit state

## Auth / email (launch)

- Login outcomes: `mayabu_auth_login_total`
- Session events: `mayabu_auth_session_events_total`
- Email: `mayabu_email_send_total{type,result}` for `verification|password_reset|password_changed`
- Wishlist mutations: `mayabu_wishlist_action_total`

## Launch alert panels (minimum)

1. `/api/ready` blackbox
2. 5xx rate
3. DB pool acquire errors / waiting
4. Queue oldest pending age
5. Worker task failure spike
6. Email send failure spike
7. Redis degraded (informational; not page-down)
