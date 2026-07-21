# Mayabu v5 Backend Architecture

## Architectural style

Mayabu uses a **modular monolith with separately deployable API, worker, and maintenance processes**. This avoids premature microservice complexity while preserving clear module boundaries and independent scaling of read traffic and browser workloads.

## Read path

```text
Client
  -> FastAPI request middleware
     -> query sanitation + rate limit
        -> Redis response cache
           -> query parser/classifier
              -> product_search_documents
                 -> SQL candidate ranking
                    -> Python business ranking
                       -> exact_matches / similar_variants / related_products
```

`product_search_documents` is a compact read model. Public search does not scan raw scrape rows or launch browsers. Every product update marks one product dirty. Workers or maintenance refresh only those dirty documents.

## Write path

```text
Discovery or direct URL
  -> durable scrape_tasks row
     -> lease-based worker claim (FOR UPDATE SKIP LOCKED)
        -> platform semaphore + circuit breaker
           -> scraper retry/backoff
              -> normalization + quality validation
                 -> one-record savepoint
                    -> listing upsert
                    -> append price observation
                    -> daily rollup
                    -> exact/family fingerprint
                    -> variant group
                    -> dirty search document
                    -> cache invalidation
```

One bad platform or listing does not abort the entire multi-platform operation.

## Modules

```text
mayabu/api/               HTTP routes and serializers
mayabu/core/              configuration, security, logging
mayabu/domain/            pure identity and relationship rules
mayabu/search/            parser, ranking, read model, cache
mayabu/services/          direct ingestion and variant grouping
mayabu/jobs/              durable queue, bounded worker, maintenance
mayabu/scrapers/          pure URL validation, detail scraping, circuit breaker
mayabu/monitoring/        health and operational reports
mayabu/db/                compatibility repository boundary
mayabu_db/                schema, ingestion, matching, queue persistence
mayabu_refresh/           existing listing price refreshers
```

## Product relationships

- **Exact product:** shared model/SKU evidence with no CPU/RAM/storage/screen conflict.
- **Similar variant:** same family but a meaningful variant dimension differs.
- **Related product:** semantically close, but not safe to compare as the same offer.
- **Conflict:** brand/category/model/spec evidence is incompatible.

Exact products may share one product cluster. Similar variants share a `variant_group` but keep separate product and offer records.

## Search storage

`product_search_documents` stores only fields needed for retrieval and cards:

- normalized title, brand, category, family, model codes
- CPU, RAM, storage, screen, GPU
- best price/platform, platform and offer counts
- image and freshness
- exact/family fingerprints and variant group
- full-text and trigram search documents

Indexes cover full text, trigram text/model codes, category/brand/family, variant group, best price, and freshness.

## Queue safety

- PostgreSQL is the queue source of truth.
- Active tasks use idempotency keys.
- Workers claim tasks with `SKIP LOCKED`.
- Running tasks have renewable leases.
- Expired leases are requeued.
- Retries use bounded exponential backoff.
- Exhausted tasks become `dead` instead of retrying forever.
- Per-platform semaphores prevent browser storms.
- Persisted circuit breakers stop repeated calls to unhealthy platforms.

## Availability behavior

- PostgreSQL failure makes readiness fail; liveness remains available.
- Redis failure disables cache/rate-limit acceleration temporarily but does not stop DB reads.
- Scraper failure never removes existing product data.
- Empty/blocked pages create diagnostics and platform-health signals.
- API and workers have independent resource limits and deployment images.

## Space controls

- Raw scrape items expire after a configured retention window.
- Raw price observations are deleted only when a daily rollup exists.
- Completed/dead jobs and old scrape runs are removed by maintenance.
- API container excludes Chromium; only worker images install browser dependencies.
- Search reads use a compact incremental table rather than raw operational tables.

## Scaling path

Scale vertically first, then independently add API and worker replicas. PostgreSQL task claims and idempotency support multiple workers. Keep per-platform global traffic within safe limits; process-local semaphores alone are not a legal or operational substitute for platform-wide quotas. At materially larger scale, a distributed rate-limit token bucket can be added in Redis without changing domain or repository interfaces.
