# Mayabu Production / Staging Readiness Matrix — Real Staging Bring-Up V1

Evidence date: 2026-09-22.

**External staging host / managed PG / managed Redis / alert webhook: UNAVAILABLE in this environment.**

| Area | Status | Evidence | Blocker |
|---|---|---|---|
| HTTPS staging | BLOCKED | No hostname/cert | Provision staging DNS+TLS |
| Managed PostgreSQL | BLOCKED | Local Docker only | Managed instance + TLS |
| Managed Redis | BLOCKED | Local Redis only | Managed TLS/auth |
| Alert delivery | NOT_CONFIGURED | `send_staging_alert.py` → NOT_CONFIGURED | `MAYABU_ALERT_WEBHOOK_URL` |
| Distributed slots (code) | PASS (unit) | Concurrent cap test + env key prefix | Multi-process on staging still BLOCKED |
| Scheduler lease (local DB) | PASS | lease DB tests | Dual-process on staging BLOCKED |
| platform_health widen | PASS | migration `2026_09_22_platform_health_platforms_widen` | — |
| Staging GO | NO-GO | — | All external P0s |
| Production GO | NO-GO | — | All external P0s |
| Limited public beta | NO-GO | Staging not up | — |

See also: `docs/STAGING_RELEASE_CHECKLIST.md`, `docs/PRODUCTION_RELEASE_CHECKLIST.md`, `docs/PROCESS_ENTRYPOINTS.md`.
