# Mayabu Staging Release Checklist

Machine + human checklist. Mark only with evidence, never from templates alone.

Statuses: PASS | PARTIAL | BLOCKED | NOT_CONFIGURED | NOT_TESTED | FAILED

## DNS / TLS

- [ ] Staging hostname provisioned
- [ ] Trusted certificate (not self-signed)
- [ ] HTTP → HTTPS redirect
- [ ] Mixed content clean
- [ ] Frontend origin configured
- [ ] API origin configured

## Secrets / config

- [ ] Secrets injected (not committed)
- [ ] `MAYABU_ENV=staging`
- [ ] No localhost public URLs (or explicit `MAYABU_ALLOW_INSECURE_LOCAL=1` for lab only)
- [ ] Cookie Secure enabled
- [ ] CORS allowlist explicit
- [ ] Admin token set

## Data

- [ ] Managed PostgreSQL (separate from prod/dev/test)
- [ ] PostgreSQL TLS proven
- [ ] Migrations applied; `/api/ready` true
- [ ] Managed Redis TLS/auth
- [ ] Redis key prefix / DB isolated
- [ ] Backup enabled
- [ ] Restore drill to separate DB PASS

## Processes

- [ ] Migration job ran before traffic
- [ ] API production process
- [ ] Frontend production build (not Vite dev)
- [ ] Worker #1 healthy heartbeat
- [ ] Scheduler A leader
- [ ] Scheduler B standby (failover proven)
- [ ] Distributed retailer slots proven with ≥2 workers

## Monitoring / alerts

- [ ] Metrics scrapeable
- [ ] Alert destination configured
- [ ] Synthetic alert delivered
- [ ] Worker-stall alert delivered
- [ ] Scheduler-stale alert delivered

## User / security proofs

- [ ] HTTPS Secure cookie
- [ ] CSRF / Origin
- [ ] CORS credentialed
- [ ] Safe `next=` redirect
- [ ] Staging noindex
- [ ] Product images under CSP

## E2E

- [ ] Production-build real-backend desktop
- [ ] Production-build real-backend mobile
- [ ] HTTPS-specific suite
- [ ] Deterministic Check Latest Price
- [ ] Controlled live retailer smoke (tiny)

## SEO

- [ ] Staging noindex
- [ ] No production sitemap pollution

## Sign-off

Staging GO requires all P0 security/data/runtime/distributed/alert gates PASS.
