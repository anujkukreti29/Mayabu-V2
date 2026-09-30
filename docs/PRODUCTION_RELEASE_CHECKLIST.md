# Mayabu Production Release Checklist

Separate from staging. Do **not** reuse staging noindex or staging hosts.

Statuses: PASS | PARTIAL | BLOCKED | NOT_CONFIGURED | NOT_TESTED | FAILED

## Host / TLS

- [ ] Production public host
- [ ] Trusted TLS + HTTP→HTTPS
- [ ] HSTS policy decided (preload only if deliberate)
- [ ] Canonical / robots / sitemap production-correct

## Secrets / config dry-run

- [ ] `MAYABU_ENV=production` validation rejects localhost / insecure cookies / `CORS=*` / insecure PG
- [ ] Required secrets present (admin, DB, Redis, email provider if required)
- [ ] No staging host in production SEO artifacts

## Data

- [ ] Managed PostgreSQL TLS
- [ ] Backups + PITR evidence
- [ ] Restore drill evidence (separate recovery DB)
- [ ] Migrations applied; readiness green
- [ ] Connection budget < provider limit with margin

## Runtime

- [ ] API replicas
- [ ] Workers (shared slots proven)
- [ ] Single scheduler leader (+ standby optional)
- [ ] Browser sandbox decision documented
- [ ] Graceful shutdown proven
- [ ] Kill switches operable

## Security user proofs

- [ ] Secure cookies over HTTPS
- [ ] CSRF / CORS
- [ ] Auth session survives API restart

## Operations

- [ ] Alert routing delivers critical pages
- [ ] Dashboard usable
- [ ] Runbooks exercised
- [ ] Rollback path understood (schema-compatible)

## Correctness sample

- [ ] Price sample exact (no known wrong public price)
- [ ] Stock sample (no accepted false OOS)
- [ ] Matching regression clean (false exact = 0)
- [ ] Check Latest Price bounded

## Sign-off

Production GO only if all P0 gates in this checklist are PASS.
Limited public beta may be considered if staging GO and production-scale evidence is still limited — never as a substitute for security/backup/alert gates.
