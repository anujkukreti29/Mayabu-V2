# Mayabu Production Checklist

- Set a strong `MAYABU_ADMIN_TOKEN` and database password.
- Restrict PostgreSQL and Redis to private networking.
- Configure exact HTTPS frontend origins; never use wildcard credentials CORS.
- Run migration and `scripts/verify_v5.py` during deployment.
- Start at worker concurrency 1-2 and increase only after observing platform health.
- Keep scraper page/product caps enabled.
- Monitor readiness, DB pool waiting, queue depth, dead jobs, open anomalies, and dirty search documents.
- Run the bounded API load test and record p95/p99 latency before launch.
- Back up PostgreSQL and test restoration.
- Verify daily rollups before reducing raw price retention.
- Review debug artifact retention and access permissions.
- Validate each platform scraper after page-layout changes.
- Never merge products across conflicting RAM, storage, CPU, screen, or model evidence.
- Use direct URL ingestion for exact listings missed by discovery.

- Confirm Redis-backed distributed scraper slots are healthy before scaling worker replicas.
- Record the active search mode from `/api/health`; production should use `v5_indexed`.
- Size `MAYABU_API_WORKERS`, `MAYABU_API_THREADPOOL_TOKENS`, and `MAYABU_DB_POOL_MAX_SIZE` together.
- Review `docs/PRODUCTION_TOPOLOGY.md` and complete a database restore drill.
- Keep the GitHub Actions backend, frontend, and deterministic E2E jobs green before merging.
