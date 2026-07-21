# Mayabu Current Working Backend Architecture

This package is the current verified Mayabu backend baseline after the latest scraper, database, API, and Croma headless fixes.

## Current verified state

The backend has been verified locally with Docker PostgreSQL and Redis, all four discovery scrapers, Croma headless discovery, Croma headless refresh, database ingestion, health reporting, and the public search API.

Latest verified local results:

- `product_clusters`: 30
- `platform_listings`: 32
- `price_observations`: 39
- `scrape_runs`: 7
- `review_queue`: 0
- `/api/search?q=laptop`: returns 20 ranked laptop results with `best_price`, `best_platform`, `platform_count`, parsed specs, and pagination metadata.

One open medium data-quality anomaly was observed: `mrp_below_price`. This is not a pipeline failure. It means one listing needs data-quality inspection or future scraper normalization improvement.

## MVP scope

Mayabu is currently a database-first Indian e-commerce price-intelligence backend for laptops.

Current supported platforms:

- Amazon India
- Flipkart
- Reliance Digital
- Croma

Current discovery fields:

- `title`
- `current_price`
- `mrp`
- `discount_percent`
- `image_url`
- `product_url`

Current refresh fields:

- `current_price`
- `mrp`
- `discount_percent`

Reviews, delivery ETA, seller-depth scoring, full specs enrichment, all images, all variants, and fake-review detection are future modules.

## High-level architecture

```text
User/API Search
    ↓
FastAPI API layer
    ↓
Query parser + classifier + DB search repository + ranker
    ↓
PostgreSQL source of truth
    ↓
product_clusters + platform_listings + price_observations + rollups
    ↑
Discovery scrapers + refresh scrapers
    ↑
Direct runner / worker / scheduler
```

## Runtime components

### 1. API layer

Location: `mayabu/api/`

Important files:

- `mayabu/api/main.py` - FastAPI app factory and route registration
- `mayabu/api/search_routes.py` - public search endpoint
- `mayabu/api/product_routes.py` - product detail and price history endpoints
- `mayabu/api/health_routes.py` - health endpoints
- `mayabu/api/admin_routes.py` - admin endpoints protected by token
- `run_api.py` - local API launcher

Working endpoints:

```text
GET /api/health
GET /api/search?q=laptop
GET /api/products/{product_id}
GET /api/products/{product_id}/price-history
```

### 2. Search layer

Location: `mayabu/search/`

Important files:

- `query_parser.py` - normalizes laptop queries and extracts brand/specs
- `query_classifier.py` - determines relevance and intent
- `search_repository.py` - PostgreSQL-backed product search
- `ranker.py` - ranking logic
- `demand_signal.py` - logs demand clusters for future scraping decisions
- `cache.py` - optional Redis JSON cache

Important behavior:

- Generic `q=laptop` now returns active laptop products through category fallback.
- Search is DB-only. User search does not directly launch live scraping.
- Demand signals are stored for controlled future task materialization.

### 3. Database layer

Current source of truth: PostgreSQL.

Location: `mayabu_db/` and `mayabu/db/`

Important files:

- `mayabu_db/schema.sql` - idempotent schema and views
- `mayabu_db/migrate.py` - applies schema
- `mayabu_db/connection.py` - DB connection helper
- `mayabu_db/ingestion.py` - discovery ingestion pipeline
- `mayabu_db/refresh_ingestion.py` - refresh result ingestion
- `mayabu_db/repository.py` - DB repository helpers, observations, rollups, anomalies
- `mayabu_db/matching.py` - cross-platform product matching
- `mayabu_db/variant.py` - variant key generation
- `mayabu_db/quality.py` - validation and anomaly classification
- `mayabu_db/health.py` - DB status summary

Core tables:

- `product_clusters` - canonical product entities
- `platform_listings` - platform-specific listings
- `price_observations` - time-series price records
- `daily_listing_prices` - daily listing rollups
- `daily_product_prices` - daily product rollups
- `scrape_tasks` - queue for discovery/refresh work
- `scrape_runs` - run history and scraper stats
- `raw_scrape_items` - raw scraper payloads for diagnostics
- `review_queue` - uncertain cross-platform match review
- `anomaly_events` - data-quality and pipeline anomalies
- `search_queries` - public search logs
- `query_demand_clusters` - demand-driven scraping candidates
- `platform_health` - platform health state
- `scrape_budget` - platform scrape budget tracking
- `worker_heartbeats` - worker liveness

Important view:

- `current_product_best_prices` - gives `best_price`, `best_platform`, and `platform_count` per active product.

### 4. Discovery scrapers

Current DB runner imports these files through `mayabu_db/scraper_runner.py`:

- `amazon_scraper.py`
- `flipkart_scraper.py`
- `croma_scraper.py`
- `reliancedigital_scraper.py`

Common scraper base:

- `mayabu_scraper_base.py`

Working behavior:

- Each discovery scraper returns normalized raw listing records.
- Health checks measure title, price, image, URL, duplicate rate, and count.
- Empty selector cases save debug artifacts.
- Croma discovery now works in headless mode and can recover from embedded/initial page data when DOM cards are not visible.

### 5. Refresh scrapers

Location: `mayabu_refresh/`

Current files:

- `mayabu_refresh/amazon.py`
- `mayabu_refresh/flipkart.py`
- `mayabu_refresh/croma.py`
- `mayabu_refresh/reliancedigital.py`
- `mayabu_refresh/common.py`
- `mayabu_refresh/models.py`
- `mayabu_refresh/runner.py`

Working behavior:

- Refresh scraper only extracts price fields.
- It intentionally avoids reviews, delivery details, all specs, and all variants.
- Discount is calculated from current price and MRP when both exist.
- Croma refresh now works in headless mode by reading SSR/initial data and falling back to DOM/text extraction.

### 6. Worker and scheduler

Important files:

- `worker_db.py` - claims pending tasks and executes discovery/refresh
- `mayabu_db/tasks.py` - task claim/fail/complete/run lifecycle
- `mayabu_db/scheduler.py` - legacy task seeding/materialization
- `mayabu/scheduler/task_materializer.py` - v4 materialization for refresh/demand
- `mayabu/scheduler/maintenance.py` - stuck task reaper, raw cleanup, demand counter refresh
- `mayabu/scheduler/budget_policy.py` - daily platform budget
- `mayabu/scheduler/platform_health_policy.py` - platform health policy
- `mayabu/scheduler/refresh_policy.py` - refresh due logic
- `mayabu/scheduler/discovery_policy.py` - discovery materialization logic

Workflows:

```text
Direct scrape → ingest immediately:
python run_mayabu_db.py "laptop" --platforms flipkart amazon reliancedigital croma --max-pages 1 --max-products 10
```

```text
Queue workflow:
python -m mayabu_db.scheduler seed-discovery --platforms flipkart croma --query "laptop" --max-pages 1 --max-products 20
python worker_db.py --once
```

```text
Refresh workflow:
python -m mayabu.scheduler.task_materializer refresh --limit 20
python worker_db.py --once
```

### 7. Monitoring and admin

Locations:

- `mayabu/monitoring/`
- `mayabu/admin/`
- `admin_review.py`

Capabilities:

- DB health summary
- scrape run tracking
- anomaly inspection
- review queue commands
- platform pause/resume
- task inspection
- worker heartbeat

Useful commands:

```text
python -m mayabu_db.health
python -m mayabu.admin.task_cli pending --limit 20
python -m mayabu.admin.data_quality_cli --status open --limit 20
python -m mayabu.admin.review_cli --limit 20
python -m mayabu.admin.platform_cli pause croma
python -m mayabu.admin.platform_cli resume croma
```

## Verified local setup

Use Windows CMD from the project root.

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
docker compose up -d
python -m mayabu_db.migrate
```

Check Docker services:

```cmd
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected:

```text
mayabu-postgres   Up ...   0.0.0.0:5433->5432/tcp
mayabu-redis      Up ...   0.0.0.0:6379->6379/tcp
```

Test DB connection:

```cmd
python -c "import psycopg; conn=psycopg.connect('postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu', connect_timeout=5); print('DB OK'); conn.close()"
```

Run smoke checks:

```cmd
python -m compileall .
python tests\smoke_backend.py
python tests\smoke_v43_scrapers.py
```

Run platform discovery health checks:

```cmd
python scraper_health_check.py --platform flipkart --type discovery --query "laptop" --max-products 10 --max-pages 1 --debug
python scraper_health_check.py --platform amazon --type discovery --query "laptop" --max-products 10 --max-pages 1 --debug
python scraper_health_check.py --platform reliancedigital --type discovery --query "laptop" --max-products 10 --max-pages 1 --debug
python scraper_health_check.py --platform croma --type discovery --query "laptop" --max-products 10 --max-pages 1 --debug
```

Run full ingestion:

```cmd
python run_mayabu_db.py "laptop" --platforms flipkart amazon reliancedigital croma --max-pages 1 --max-products 10
```

Check health:

```cmd
python -m mayabu_db.health
```

Start API:

```cmd
python run_api.py
```

Test API from another terminal:

```cmd
curl "http://127.0.0.1:8000/api/health"
curl "http://127.0.0.1:8000/api/search?q=laptop"
```

## Current known non-blockers

1. Some discovery health checks can show `degraded` with reason `low_product_count` even when quality rates are `1.0`. This usually means deduping/filtering reduced valid count below 10. It is not a crash.
2. One `mrp_below_price` anomaly was observed. This should be inspected later, but it does not block the backend.
3. `.env` is intentionally excluded from this clean package. Copy `.env.example` to `.env` locally.
4. The root contains some legacy compatibility scripts (`Amazon.py`, `Flipkart.py`, `croma.py`, `reliancedigital.py`, `run_mayabu.py`, `merger.py`). The current DB-first backend uses the `*_scraper.py`, `mayabu_refresh/`, `mayabu_db/`, and `mayabu/` modules.

## Recommended next development order

1. Add frontend integration against `/api/search` and product detail endpoints.
2. Add pagination/infinite scroll UI using `limit`, `offset`, and `has_more`.
3. Add product detail page with price history from DB.
4. Add anomaly admin screen for `anomaly_events`.
5. Add scheduled refresh loop using `worker_db.py --loop` after local stability.
6. Add mobile category only after laptop scraper quality remains stable.
7. Add seller reliability, review analysis, and buy/wait recommendation as separate modules after data quality is solid.

## Architecture decision to preserve

Do not let public search directly scrape live websites. Public search should query PostgreSQL only, log demand, and let controlled schedulers/workers decide what to scrape. This keeps the product scalable, safe, and easier to debug.

## v5.3 scale-safety addendum

Mayabu v5.3 preserves the v5.2 API, schema, matching, queue, and verification
contracts while closing the horizontal worker-scaling gap found by the
independent backend audit.

- All scraper task types share one renewable Redis-backed per-platform lease.
- Production workers fail closed if distributed coordination is unavailable.
- Worker IDs default to the container or host name so replicated workers do not
  share lease-owner identities.
- Search mode is explicit in startup logs and `/api/health`.
- API sync-thread capacity is configurable and reported with DB-pool sizing.
- Backend and frontend checks run automatically in GitHub Actions.
- Dynamic administrative SQL identifiers use `psycopg.sql.Identifier` and fixed
  whitelists.

The local Compose stack remains a development/single-node environment. Use the
availability and connection-budget guidance in `docs/PRODUCTION_TOPOLOGY.md`
before production scale-out.

## v5.4 optimized-baseline addendum

Mayabu v5.4 keeps the v5.3 API, PostgreSQL schema, matching ownership,
durable queue, verification admission rules, and React Router SSR architecture.
It is a compatibility-focused refinement rather than a redesign.

The main changes are:

- every scraper entry point now uses one reusable local plus Redis-backed
  platform-capacity component;
- distributed and durable task leases are renewable, and active work stops if
  ownership is lost;
- task lease duration, renewal interval, browser headless mode, and scraper
  debug artifacts are configuration-driven;
- fuzzy title comparison is bounded and malformed numeric specifications are
  handled conservatively instead of raising conversion errors;
- search analytics and optional repository-tier failures use structured logs;
- frontend route definitions, navigation, trust copy, price statistics, and
  buying insights are reusable modules;
- the price-history chart is a small accessible SVG implementation rather than
  a large chart-runtime dependency;
- API timeouts and caller cancellation are separated, cleaned up, and tested;
- verification state is reset per product and polling failures surface as a
  real unavailable state instead of remaining queued until expiry.

No database migration or public endpoint change is required for v5.4.

## v5.5 refined-baseline addendum

Mayabu v5.5 preserves the v5.4 schema, APIs, matching ownership, queue model,
Redis coordination, and frontend routes. The release optimizes only bounded hot
paths and incremental-maintenance safety:

- legacy in-process search ranking prepares query tokens once per result page;
- visible-price classification uses reusable pure helpers and bounded candidate maps;
- frontend comparison and verification session data is validated and capped;
- native browser relative-time formatting replaces an external date dependency;
- frontend test concurrency is bounded for predictable CI memory use.

No database migration or public endpoint change is required for v5.5.
