# Mayabu Launch Checklist

Statuses (strict): `PASS` | `LOCAL PASS` | `REAL STAGING PASS` | `BLOCKED` | `MANUAL EXTERNAL STEP` | `NOT TESTED`

Do not mark BLOCKED as PASS. Do not use vague “should work” wording.

## Infrastructure

| Gate | Status | Notes |
|------|--------|-------|
| Environment matrix documented | PASS | development/test/staging/production |
| Production config fail-fast | PASS | localhost/email/CORS/admin validated |
| Staging insecure local opt-in | PASS | `MAYABU_ALLOW_INSECURE_LOCAL` |
| Secret classification | PASS | no email/DB secrets in VITE_* |
| Env templates | PASS | `.env.example` + staging/production examples |
| Reverse proxy same-origin plan | PASS | `docs/nginx.mayabu.example.conf` + DEPLOYMENT.md |
| Real HTTPS staging host | BLOCKED | no owned staging hostname/DNS/TLS in this workspace |
| Trusted TLS certificate | BLOCKED | depends on real HTTPS staging |
| Managed Postgres provisioned | MANUAL EXTERNAL STEP | local Docker PG ≠ managed proof |
| Managed Redis provisioned | MANUAL EXTERNAL STEP | local Redis ≠ managed/`rediss://` proof |

## Database

| Gate | Status | Notes |
|------|--------|-------|
| Migration runner + ledger | PASS | `python -m mayabu_db.migrate` |
| Fresh/existing upgrade path | PASS | idempotent schema + pending files |
| Pool sizing documented | PASS | workers × pool_max |
| Backup script | PASS | `scripts/backup_postgres.py` (+ Docker `pg_dump` workaround) |
| Restore script (non-primary) | PASS | `scripts/restore_postgres.py` |
| Backup→restore drill executed | LOCAL PASS | 2026-09-20: `mayabu_test` → `mayabu_restore_drill` via Docker `pg_dump`/`pg_restore`; backup 0.6s / 596244 bytes; restore 2s; counts matched (205 products, 278 listings, 386 observations, 171 users, 8 wishlist, 234 sessions, 6 migrations) |
| Managed PITR enabled | MANUAL EXTERNAL STEP | provider dashboard |

## Redis

| Gate | Status | Notes |
|------|--------|-------|
| `rediss://` supported via URL | PASS | redis-py from_url |
| Fail-open cache documented | PASS | |
| Redis-down local/staging test | NOT TESTED | no managed Redis outage window this run |
| Distributed rate-limit (2+ workers) | NOT TESTED | needs staging multi-worker + Redis |

## Auth / Email

| Gate | Status | Notes |
|------|--------|-------|
| Resend adapter implemented | PASS | Account V2 |
| Production email env validated | PASS | startup fail without key |
| Real Resend credentials | BLOCKED | no `MAYABU_AUTH_EMAIL_API_KEY` / verified domain in workspace |
| Verification email inbox proof | BLOCKED | needs Resend + real inbox |
| Reset + password-changed proof | BLOCKED | needs Resend + real inbox |
| Local Account V2 critical path | LOCAL PASS | `scripts/local_auth_critical_path.py` — signup→verify→logout→login→wishlist persist→forgot→reset→old reject→new login→sessions→logout-all |
| HTTPS Secure cookie proof | BLOCKED | needs real HTTPS staging |
| CSRF same-origin staging proof | BLOCKED | needs HTTPS staging |
| Dev inbox isolated in staging/prod | PASS | `/api/auth/dev/*` 404 when disabled / production |

## Frontend / Backend runtime

| Gate | Status | Notes |
|------|--------|-------|
| `npm run validate` | PASS | re-run this iteration |
| Production build (not Vite dev) for deploy | PASS | CI builds SSR; staging host still BLOCKED |
| API without reload in prod | PASS | `run_api.py` |
| Worker supervised service unit | PASS | `deploy/mayabu-worker.service` + compose `restart: unless-stopped` |
| Worker heartbeat visibility | PASS | `/api/health` → `worker_status`, `workers_seen_recently`, queue lag |
| Metrics protected | PASS | admin token; public → 401 locally |
| Detailed health protected | PASS | staging/prod policy |
| Private Cache-Control SSR | PASS | root headers |
| Release smoke script | PASS | `scripts/release_smoke.py` (+ product/verify enqueue flags) |
| Staging doctor | PASS | `scripts/staging_doctor.py` (read-only) |

## SEO

| Gate | Status | Notes |
|------|--------|-------|
| Staging noindex design | PASS | SEO V2 |
| Staging noindex observed (local FE) | LOCAL PASS | `x-robots-tag: noindex, nofollow` + robots hint via staging_doctor on local FE |
| Production robots/sitemap design | PASS | |
| Production host robots live check | BLOCKED | no production host yet |
| Search Console submission | MANUAL EXTERNAL STEP | |

## Monitoring

| Gate | Status | Notes |
|------|--------|-------|
| Dashboard panels documented | PASS | OBSERVABILITY_DASHBOARD.md |
| Launch alerts documented | PASS | OPERATIONS_RUNBOOK.md |
| Monitoring scrape wired | MANUAL EXTERNAL STEP | connect Prometheus/vendor to protected `/api/metrics` |
| Alert delivery proof | BLOCKED | no monitoring vendor wired in this workspace |
| Error monitoring vendor | NOT TESTED | structured logs ready; vendor optional |

## Workers / Scrapers

| Gate | Status | Notes |
|------|--------|-------|
| Worker separate process | PASS | |
| Platform readiness unchanged | PASS | JioMart/Bajaj not enabled |
| Worker-absent → queue grows → recovery | LOCAL PASS | stop worker → verify queued pending age↑ → restart → task claimed/running |
| TWS verify-price final result | LOCAL PASS | was DB `IndeterminateDatatype` on NULL price CASE; fixed casts; Croma Nord Buds 3r completed `out_of_stock` in ~29s (playwright); price 1999 preserved |

## E2E / Validation

| Gate | Status | Notes |
|------|--------|-------|
| Backend pytest ×2 | PASS | 220 passed ×2 (2026-09-20) |
| Frontend validate | PASS | |
| Release smoke local FE+BE | LOCAL PASS | live/ready/homepage/search/category/health/metrics + FE routes |
| Desktop full journey on HTTPS staging | BLOCKED | no HTTPS staging |
| Mobile full journey on HTTPS staging | BLOCKED | no HTTPS staging |
| Real email journeys | BLOCKED | external credentials |
| npm audit (prod) | LOCAL PASS | 4 high (react-router RSC CSRF — upgrade path exists, not forced this run); 4 moderate (qs/express). Not treated as instant launch GO without staging HTTPS proof; classify before prod GO |

## Rollback / Incident

| Gate | Status | Notes |
|------|--------|-------|
| Deployment runbook | PASS | DEPLOYMENT.md |
| Backup/restore runbook | PASS | BACKUP_RESTORE.md |
| Incident procedures | PASS | OPERATIONS_RUNBOOK.md (updated with staging findings) |
| Rollback plan | PASS | DEPLOYMENT.md |

## Verdicts

| Question | Answer |
|----------|--------|
| Local/code ready? | **YES** |
| Real HTTPS staging proven? | **NO** |
| Production-ready? | **NO — NO-GO** |

### Exact blockers before production launch

1. Provision real HTTPS staging host + DNS + trusted TLS + reverse proxy
2. Configure Resend sending domain (SPF/DKIM) + API key; prove verification + reset inbox delivery
3. Prove Secure cookies + CSRF/Origin over HTTPS
4. Connect managed Postgres + Redis (TLS) — not local Docker as proof
5. Execute backup→restore on managed staging DB; enable PITR
6. Wire monitoring scrape of protected `/api/metrics` + prove at least one alert
7. Production-build desktop + mobile E2E against real staging URL
8. Production host SEO live verification + Search Console (manual)
9. Revisit react-router high advisories before public launch (patch when compatible)
