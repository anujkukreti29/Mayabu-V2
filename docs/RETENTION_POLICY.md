# Mayabu retention policy (initial)

These are operational defaults for staging/production. Adjust with measured growth.

| Store | Retention | Notes |
|---|---|---|
| Auth sessions | Expire per `MAYABU_AUTH_SESSION_DAYS` (default 30d); cleanup job removes expired rows | Do not unbounded-grow |
| Watch events | Keep ≥90 days user-visible; archive/delete older after review | Do not delete events still needed for recent watches |
| Completed scrape_tasks | Keep 14–30 days for ops evidence; never delete pending/running | Archive completed/dead only |
| Price observations | **Keep** — core product history | Prefer rollups (`daily_*`) before any purge |
| Live verification events | `MAYABU_LIVE_VERIFICATION_EVENT_RETENTION_DAYS` (default 30) | |
| Debug artifacts / raw HTML | Short retention (days), access-controlled | |

Maintenance entrypoint: `run_maintenance_scheduler.py` / maintenance compose profile.
