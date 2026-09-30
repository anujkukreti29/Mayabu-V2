# Mayabu staging preflight (prepare — do not claim ready)

This checklist is the gate before **MAYABU STAGING & PRODUCTION INFRASTRUCTURE READINESS V1**.
Passing local/multi-store quality work does **not** satisfy these items.

Statuses used elsewhere: `NOT_CONFIGURED` | `BLOCKED` | `PARTIAL` | `PASS` | `DEFERRED`

## HTTPS / origins

- [ ] Dedicated staging hostname (not localhost) — **BLOCKED** (no external host provisioned)
- [ ] Trusted TLS certificate on the edge (not self-signed in browsers under test) — **BLOCKED**
- [ ] Frontend origin and API origin documented and allowlisted — templates in `.env.staging.example`
- [ ] Cookie `Secure` + appropriate `SameSite` over HTTPS — code defaults exist; HTTPS proof **BLOCKED**
- [ ] CSRF / origin checks enabled for mutating auth routes — unit/integration exist; HTTPS proof **BLOCKED**

## Data stores

- [ ] Managed PostgreSQL with TLS required — **BLOCKED** (local Docker PG only)
- [x] Migrate-from-zero on fresh DB → schema ok / readiness ready (local `mayabu_migrate_zero`, 2026-09-22)
- [ ] Managed Redis with TLS required — **BLOCKED**
- [x] Secrets not committed; injected via environment/secret manager (templates only)
- [ ] Automated backups + PITR enabled (external proof) — **BLOCKED**
- [x] Local restore drill documented (`docs/BACKUP_RESTORE.md`) — managed restore **BLOCKED**

## Application topology (evidence-based starting point)

| Role | Starting recommendation | Evidence |
|---|---|---|
| API | 1 host, 1–2 Uvicorn workers | compose + topology doc |
| Worker | 1 replica, concurrency 1–2 | Playwright + browser pool; Chromium is child-process heavy |
| Scheduler | 1 replica with DB lease; extras standby | `tests/test_scheduler_lease_db.py` **4 passed** (leader/standby/failover) |
| Browser concurrency | platform concurrency 1–2 | distributed Redis slots; Amazon challenge-sensitive |
| Redis | Required in staging/prod for slots/rate-limit | fail-open cache; fail-closed verify slots in prod |
| PostgreSQL | Managed + pooler when process count grows | pool defaults 10/process; budget in topology doc |

## Process / health (local proofs)

- [x] Distinct processes: api / worker / scheduler / maintenance (`docker-compose.yml` profiles)
- [x] `/api/live` vs `/api/ready` vs `/api/health` (readiness requires PG + schema; Redis optional)
- [x] Incomplete migrations → `not_ready` / `database_migrations_incomplete`
- [x] Queue stall + user_verify stall signals in `/api/health.automation`
- [x] Scheduler advisory-lock failover unit/DB proof
- [ ] Dual scheduler replicas on real staging host — **BLOCKED**
- [ ] Metrics/alerting wired to a pager — **NOT_CONFIGURED**

## SEO / email

- [x] Staging expected noindex via `VITE_APP_ENV=staging` (code path)
- [ ] Resend/domain verified — **DEFERRED / BLOCKED**

## Explicit non-claims

- Local `npm run validate` and Playwright green ≠ staging ready
- Catalog multi-store quality ≠ infrastructure ready
- Self-signed TLS / hosts-file staging ≠ production readiness
- Scheduler lease unit tests ≠ live staging dual-replica proof

## External blockers (remain NO-GO until proven)

1. Trusted HTTPS staging host
2. Managed PostgreSQL + TLS + backups/PITR + restore drill
3. Managed Redis + TLS
4. Secure cookies over HTTPS + CSRF/origin browser proof
5. Production-build E2E against staging HTTPS origin
6. Alert routing + dual-scheduler live failover on staging
7. Distributed worker crash/reclaim on staging
