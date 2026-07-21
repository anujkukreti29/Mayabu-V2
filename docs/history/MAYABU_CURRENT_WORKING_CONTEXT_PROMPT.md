# Mayabu v5.2 continuation context

Mayabu is a database-first AI buying assistant for laptops and later mobiles across Amazon India, Flipkart, Croma, and Reliance Digital. The active backend baseline is Mayabu v5.2.

Architecture rules:
- Public search reads PostgreSQL/Redis only and never launches a scraper.
- Scraping uses durable PostgreSQL tasks, bounded workers, platform circuit breakers, and Redis cross-process platform slots.
- Exact matching is deterministic; storage/RAM/model variants are grouped but not incorrectly merged.
- Live price verification is explicit user action. It shows cached prices immediately, coalesces same-product bursts in Redis, enforces stable one-task-per-listing idempotency in PostgreSQL, globally smooths different-product bursts, and verifies the best offer by default.
- User IP addresses are never used as scraping proxies. Forwarding headers are ignored unless a trusted reverse proxy is explicitly configured.
- Verification tries lightweight structured HTML first and falls back to Playwright.
- One platform failure must not crash the whole system.
- Keep Windows CMD instructions and prefer patch-only upgrades for small changes.

Important commands:
```cmd
set DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu
set REDIS_URL=redis://127.0.0.1:6379/0
docker compose up -d postgres redis
python -m mayabu_db.migrate
python scripts\verify_v52.py
python run_api.py
python worker_db.py --loop --concurrency 2
```

Frontend product pages expose Verify current price and Verify all offers. Continue from v5.2 without rewriting stable modules unnecessarily.
