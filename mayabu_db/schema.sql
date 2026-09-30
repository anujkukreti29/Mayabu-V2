-- Mayabu database-first backend schema.
-- PostgreSQL is the source of truth. JSON is only an import/export format.

create extension if not exists pgcrypto;

create table if not exists schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);

create table if not exists product_clusters (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  brand text,
  canonical_title text not null,
  title_norm text,
  variant_key text,
  specs jsonb not null default '{}'::jsonb,
  status text not null default 'active' check (status in ('active','hidden','duplicate','needs_review','archived')),
  quality_score numeric(6,2) not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (variant_key)
);

create index if not exists idx_product_clusters_category_brand on product_clusters(category, brand);
create index if not exists idx_product_clusters_status on product_clusters(status);
create index if not exists idx_product_clusters_specs_gin on product_clusters using gin(specs);
create index if not exists idx_product_clusters_updated_at on product_clusters(updated_at desc);

create table if not exists platform_listings (
  id uuid primary key default gen_random_uuid(),
  product_id uuid references product_clusters(id) on delete set null,
  platform text not null check (platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')),
  listing_id text not null unique,
  native_id text,
  listing_url text not null,
  listing_url_hash text not null,
  title text not null,
  title_norm text,
  image_url text,
  category text not null default 'unknown',
  specs jsonb not null default '{}'::jsonb,
  current_price numeric(12,2),
  current_mrp numeric(12,2),
  current_discount_pct numeric(6,2),
  current_effective_price numeric(12,2),
  stock_status text not null default 'unknown' check (stock_status in ('in_stock','out_of_stock','unknown','unavailable')),
  seller_name text,
  match_status text not null default 'unmatched' check (match_status in ('matched','unmatched','needs_review','rejected','duplicate')),
  match_confidence numeric(7,2) not null default 0,
  match_method text,
  match_evidence jsonb not null default '{}'::jsonb,
  quality_flags jsonb not null default '[]'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_successful_refresh_at timestamptz,
  last_refresh_error text,
  refresh_priority integer not null default 100,
  refresh_interval_minutes integer not null default 720,
  last_price_change_at timestamptz,
  observation_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (platform, native_id)
);

create index if not exists idx_platform_listings_product on platform_listings(product_id);
create index if not exists idx_platform_listings_platform_last_seen on platform_listings(platform, last_seen_at desc);
create index if not exists idx_platform_listings_price on platform_listings(category, current_price);
create index if not exists idx_platform_listings_match_status on platform_listings(match_status);
create index if not exists idx_platform_listings_url_hash on platform_listings(platform, listing_url_hash);
create index if not exists idx_platform_listings_specs_gin on platform_listings using gin(specs);

create table if not exists scrape_tasks (
  id uuid primary key default gen_random_uuid(),
  platform text not null check (platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')),
  task_type text not null check (task_type in ('discovery','refresh_listing','diagnostic')),
  query text,
  url text,
  native_id text,
  max_pages integer,
  max_products integer,
  priority integer not null default 100,
  status text not null default 'pending' check (status in ('pending','running','completed','failed','dead','cancelled')),
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  scheduled_at timestamptz not null default now(),
  locked_at timestamptz,
  locked_by text,
  last_error text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_scrape_tasks_claim on scrape_tasks(status, scheduled_at, priority);
create index if not exists idx_scrape_tasks_platform on scrape_tasks(platform, task_type, status);

create table if not exists scrape_runs (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references scrape_tasks(id) on delete set null,
  platform text not null,
  task_type text not null,
  query text,
  url text,
  status text not null default 'running' check (status in ('running','completed','failed','empty','partial')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  pages_attempted integer not null default 0,
  pages_success integer not null default 0,
  raw_items integer not null default 0,
  valid_items integer not null default 0,
  listings_created integer not null default 0,
  listings_updated integer not null default 0,
  products_created integer not null default 0,
  products_matched integer not null default 0,
  observations_added integer not null default 0,
  review_items integer not null default 0,
  anomaly_count integer not null default 0,
  error_count integer not null default 0,
  error_summary text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_scrape_runs_platform_started on scrape_runs(platform, started_at desc);
create index if not exists idx_scrape_runs_status on scrape_runs(status);

create table if not exists raw_scrape_items (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references scrape_runs(id) on delete cascade,
  task_id uuid references scrape_tasks(id) on delete set null,
  platform text not null,
  query text,
  listing_id text,
  raw_payload jsonb not null,
  raw_html_path text,
  screenshot_path text,
  parse_status text not null default 'pending' check (parse_status in ('pending','valid','invalid','error')),
  parse_error text,
  scraped_at timestamptz not null default now()
);

create index if not exists idx_raw_scrape_items_run on raw_scrape_items(run_id);
create index if not exists idx_raw_scrape_items_listing on raw_scrape_items(listing_id);

create table if not exists price_observations (
  id uuid primary key default gen_random_uuid(),
  observation_hash text not null unique,
  listing_id uuid not null references platform_listings(id) on delete cascade,
  product_id uuid references product_clusters(id) on delete set null,
  platform text not null,
  observed_at timestamptz not null,
  price numeric(12,2),
  mrp numeric(12,2),
  discount_pct numeric(6,2),
  effective_price numeric(12,2),
  raw_price_text text,
  raw_mrp_text text,
  validation_status text not null default 'valid',
  stock_status text not null default 'unknown',
  seller_name text,
  source_run_id uuid references scrape_runs(id) on delete set null,
  event_type text not null default 'initial' check (event_type in ('initial','drop','rise','unchanged','back_in_stock','out_of_stock','unknown')),
  quality_flags jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_price_obs_listing_time on price_observations(listing_id, observed_at desc);
create index if not exists idx_price_obs_product_time on price_observations(product_id, observed_at desc);
create index if not exists idx_price_obs_platform_time on price_observations(platform, observed_at desc);
create index if not exists idx_price_obs_price on price_observations(price);

create table if not exists daily_listing_prices (
  listing_id uuid not null references platform_listings(id) on delete cascade,
  product_id uuid references product_clusters(id) on delete set null,
  platform text not null,
  date date not null,
  open_price numeric(12,2),
  close_price numeric(12,2),
  min_price numeric(12,2),
  max_price numeric(12,2),
  last_mrp numeric(12,2),
  observations_count integer not null default 0,
  in_stock_count integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (listing_id, date)
);

create index if not exists idx_daily_listing_prices_product_date on daily_listing_prices(product_id, date desc);
create index if not exists idx_daily_listing_prices_platform_date on daily_listing_prices(platform, date desc);

create table if not exists daily_product_prices (
  product_id uuid not null references product_clusters(id) on delete cascade,
  date date not null,
  best_price numeric(12,2),
  best_platform text,
  amazon_price numeric(12,2),
  flipkart_price numeric(12,2),
  croma_price numeric(12,2),
  reliancedigital_price numeric(12,2),
  platform_count integer not null default 0,
  observations_count integer not null default 0,
  all_time_low_so_far numeric(12,2),
  updated_at timestamptz not null default now(),
  primary key (product_id, date)
);

create index if not exists idx_daily_product_prices_date on daily_product_prices(date desc);
create index if not exists idx_daily_product_prices_best on daily_product_prices(best_price);

create table if not exists review_queue (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references platform_listings(id) on delete cascade,
  candidate_product_id uuid references product_clusters(id) on delete set null,
  score numeric(7,2),
  evidence jsonb not null default '{}'::jsonb,
  status text not null default 'needs_review' check (status in ('needs_review','approved','rejected','ignored','resolved')),
  reviewer_note text,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  unique (listing_id, candidate_product_id, status)
);

create index if not exists idx_review_queue_status on review_queue(status, created_at);

create table if not exists anomaly_events (
  id uuid primary key default gen_random_uuid(),
  severity text not null check (severity in ('low','medium','high','critical')),
  event_type text not null,
  platform text,
  product_id uuid references product_clusters(id) on delete set null,
  listing_id uuid references platform_listings(id) on delete set null,
  run_id uuid references scrape_runs(id) on delete set null,
  message text not null,
  evidence jsonb not null default '{}'::jsonb,
  status text not null default 'open' check (status in ('open','acknowledged','resolved','ignored')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists idx_anomaly_events_status on anomaly_events(status, severity, created_at desc);
create index if not exists idx_anomaly_events_run on anomaly_events(run_id);

create table if not exists scraper_diagnostics (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references scrape_runs(id) on delete cascade,
  task_id uuid references scrape_tasks(id) on delete set null,
  platform text not null,
  url text,
  stage text not null,
  severity text not null default 'info' check (severity in ('info','warning','error','critical')),
  message text not null,
  screenshot_path text,
  html_path text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_scraper_diagnostics_run on scraper_diagnostics(run_id, created_at);

create table if not exists scheduler_plans (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  platform text not null check (platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')),
  task_type text not null check (task_type in ('discovery','refresh_listing','diagnostic')),
  query text,
  cadence_minutes integer not null,
  priority integer not null default 100,
  max_pages integer,
  max_products integer,
  enabled boolean not null default true,
  last_materialized_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists price_alerts (
  id uuid primary key default gen_random_uuid(),
  user_ref text not null,
  product_id uuid not null references product_clusters(id) on delete cascade,
  target_price numeric(12,2) not null,
  status text not null default 'active' check (status in ('active','triggered','paused','cancelled')),
  created_at timestamptz not null default now(),
  triggered_at timestamptz
);


-- Idempotent v3.2 refresh-price extensions for existing v3.1 databases.
alter table platform_listings add column if not exists current_effective_price numeric(12,2);
alter table platform_listings add column if not exists last_successful_refresh_at timestamptz;
alter table platform_listings add column if not exists last_refresh_error text;
alter table platform_listings add column if not exists refresh_priority integer not null default 100;
alter table platform_listings add column if not exists refresh_interval_minutes integer not null default 720;
alter table price_observations add column if not exists effective_price numeric(12,2);
alter table price_observations add column if not exists raw_price_text text;
alter table price_observations add column if not exists raw_mrp_text text;
alter table price_observations add column if not exists validation_status text not null default 'valid';
create index if not exists idx_platform_listings_refresh_due on platform_listings(platform, stock_status, last_successful_refresh_at, refresh_priority);

create or replace view current_product_best_prices as
select
  p.id as product_id,
  p.category,
  p.brand,
  p.canonical_title,
  p.specs,
  min(l.current_price) filter (where l.current_price is not null and l.stock_status <> 'out_of_stock') as best_price,
  (array_agg(l.platform order by l.current_price asc nulls last))[1] as best_platform,
  count(distinct l.platform) filter (where l.current_price is not null) as platform_count,
  max(l.last_seen_at) as last_seen_at
from product_clusters p
left join platform_listings l on l.product_id = p.id and l.match_status = 'matched'
where p.status = 'active'
group by p.id;

-- v4 full backend architecture extensions. Safe, idempotent additions.
alter table product_clusters add column if not exists model_code text;
alter table product_clusters add column if not exists confidence_score numeric(7,2) not null default 0;
alter table platform_listings add column if not exists currency text not null default 'INR';
alter table scrape_tasks add column if not exists platform_listing_id uuid references platform_listings(id) on delete set null;

-- Broaden task type/status constraints for the long-term architecture while keeping old names compatible.
-- Keep the full allow-list here: intermediate narrower checks break re-apply when verify_listing rows exist.
alter table scrape_tasks drop constraint if exists scrape_tasks_task_type_check;
alter table scrape_tasks add constraint scrape_tasks_task_type_check check (
  task_type in (
    'discovery','discovery_search','refresh_listing','refresh_hot_product',
    'retry_failed','enrichment','enrich_listing','targeted_discovery','diagnostic',
    'direct_ingest','index_product','maintenance','verify_listing'
  )
);
alter table scrape_tasks drop constraint if exists scrape_tasks_status_check;
alter table scrape_tasks add constraint scrape_tasks_status_check check (status in ('pending','running','completed','failed','dead','cancelled','paused'));
alter table scrape_runs drop constraint if exists scrape_runs_task_type_check;
alter table scheduler_plans drop constraint if exists scheduler_plans_task_type_check;
alter table scheduler_plans add constraint scheduler_plans_task_type_check check (
  task_type in (
    'discovery','discovery_search','refresh_listing','refresh_hot_product',
    'retry_failed','enrichment','enrich_listing','targeted_discovery','diagnostic',
    'direct_ingest','index_product','maintenance','verify_listing'
  )
);

create table if not exists search_queries (
  id uuid primary key default gen_random_uuid(),
  raw_query text not null,
  normalized_query text not null,
  detected_category text,
  detected_brand text,
  detected_specs jsonb not null default '{}'::jsonb,
  result_count integer not null default 0,
  top_product_id uuid references product_clusters(id) on delete set null,
  confidence numeric(7,2) not null default 0,
  ip_hash text,
  session_hash text,
  created_at timestamptz not null default now()
);
create index if not exists idx_search_queries_normalized_created on search_queries(normalized_query, created_at desc);
create index if not exists idx_search_queries_zero_result on search_queries(result_count, created_at desc);

create table if not exists query_demand_clusters (
  id uuid primary key default gen_random_uuid(),
  canonical_query text not null,
  normalized_query text not null unique,
  detected_category text,
  detected_brand text,
  detected_specs jsonb not null default '{}'::jsonb,
  query_count_24h integer not null default 0,
  query_count_7d integer not null default 0,
  unique_user_count_24h integer not null default 0,
  best_matching_product_id uuid references product_clusters(id) on delete set null,
  coverage_status text not null default 'unknown' check (coverage_status in ('unknown','covered','partial','missing','irrelevant')),
  priority_score numeric(7,2) not null default 0,
  last_seen_at timestamptz not null default now(),
  last_promoted_at timestamptz,
  status text not null default 'active' check (status in ('active','ignored','promoted','paused')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_query_demand_priority on query_demand_clusters(status, coverage_status, priority_score desc, last_seen_at desc);
create index if not exists idx_query_demand_brand on query_demand_clusters(detected_brand);

create table if not exists scrape_budget (
  id uuid primary key default gen_random_uuid(),
  platform text not null check (platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')),
  budget_date date not null,
  discovery_budget integer not null,
  refresh_budget integer not null,
  discovery_used integer not null default 0,
  refresh_used integer not null default 0,
  health_status text not null default 'healthy',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(platform, budget_date)
);
create index if not exists idx_scrape_budget_date on scrape_budget(budget_date desc, platform);

create table if not exists platform_health (
  platform text primary key check (platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')),
  status text not null default 'healthy' check (status in ('healthy','degraded','blocked','paused')),
  reason text,
  block_rate numeric(7,4) not null default 0,
  empty_rate numeric(7,4) not null default 0,
  failure_rate numeric(7,4) not null default 0,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  updated_at timestamptz not null default now()
);
-- Widen check before seed inserts. Older DBs may still have a narrower
-- platform_health_platform_check that rejects vijaysales/poorvika/etc.
alter table platform_health drop constraint if exists platform_health_platform_check;
alter table platform_health add constraint platform_health_platform_check check (
  platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')
);
insert into platform_health(platform)
values ('amazon'), ('flipkart'), ('croma'), ('reliancedigital'), ('vijaysales'), ('jiomart'), ('poorvika'), ('bajajelectronics')
on conflict (platform) do nothing;

-- Helpful search indexes. pg_trgm is optional but useful for fuzzy title queries.
create extension if not exists pg_trgm;
create index if not exists idx_product_clusters_title_trgm on product_clusters using gin(title_norm gin_trgm_ops);
create index if not exists idx_platform_listings_title_trgm on platform_listings using gin(title_norm gin_trgm_ops);
create index if not exists idx_scrape_tasks_platform_listing on scrape_tasks(platform_listing_id);
create index if not exists idx_platform_listings_currency on platform_listings(currency);


-- v4.1 hardening additions. Safe, idempotent, and compatible with existing v4 data.
alter table price_observations add column if not exists currency text not null default 'INR';
create index if not exists idx_price_obs_currency_time on price_observations(currency, observed_at desc);
create index if not exists idx_raw_scrape_items_scraped_at on raw_scrape_items(scraped_at);
create index if not exists idx_scrape_tasks_running_locked on scrape_tasks(status, locked_at) where status = 'running';
create index if not exists idx_search_queries_created_at on search_queries(created_at desc);
create index if not exists idx_search_queries_user_window on search_queries(normalized_query, created_at desc, ip_hash, session_hash);

create table if not exists worker_heartbeats (
  worker_id text primary key,
  last_heartbeat_at timestamptz not null default now(),
  tasks_processed_total integer not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists idx_worker_heartbeats_last on worker_heartbeats(last_heartbeat_at desc);

alter table product_clusters add column if not exists search_tsv tsvector generated always as (
  to_tsvector('english', coalesce(canonical_title, '') || ' ' || coalesce(brand, ''))
) stored;
create index if not exists idx_product_clusters_search_tsv on product_clusters using gin(search_tsv);

-- Public-offer gate used by best-price view and search-document refresh.
-- Keep in sync with mayabu.platforms.coverage production cells.
create or replace function mayabu_listing_is_public_offer(
  p_platform text,
  p_category text
) returns boolean
language sql
immutable
as $$
  select case
    when p_platform in ('amazon', 'flipkart', 'croma', 'reliancedigital') then true
    when p_platform = 'vijaysales' and p_category in (
      'laptop', 'smartphone', 'television', 'refrigerator', 'washing_machine', 'camera'
    ) then true
    when p_platform = 'poorvika' and p_category in ('laptop', 'smartphone') then true
    else false
  end;
$$;

create or replace function mayabu_listing_is_public_priced(
  p_platform text,
  p_category text,
  p_match_status text,
  p_current_price numeric,
  p_currency text
) returns boolean
language sql
immutable
as $$
  select p_match_status = 'matched'
     and p_current_price is not null
     and p_current_price > 0
     and coalesce(p_currency, 'INR') = 'INR'
     and mayabu_listing_is_public_offer(p_platform, p_category);
$$;

create or replace view current_product_best_prices as
select
  p.id as product_id,
  p.category,
  p.brand,
  p.canonical_title,
  p.specs,
  coalesce(
    min(l.current_price) filter (
      where mayabu_listing_is_public_priced(
              l.platform, p.category, l.match_status, l.current_price, l.currency
            )
        and l.stock_status <> 'out_of_stock'
    ),
    min(l.current_price) filter (
      where mayabu_listing_is_public_priced(
              l.platform, p.category, l.match_status, l.current_price, l.currency
            )
    )
  ) as best_price,
  coalesce(
    (array_agg(l.platform order by l.current_price asc nulls last) filter (
      where mayabu_listing_is_public_priced(
              l.platform, p.category, l.match_status, l.current_price, l.currency
            )
        and l.stock_status <> 'out_of_stock'
    ))[1],
    (array_agg(l.platform order by l.current_price asc nulls last) filter (
      where mayabu_listing_is_public_priced(
              l.platform, p.category, l.match_status, l.current_price, l.currency
            )
    ))[1]
  ) as best_platform,
  count(distinct l.platform) filter (
    where mayabu_listing_is_public_priced(
            l.platform, p.category, l.match_status, l.current_price, l.currency
          )
  ) as platform_count,
  max(l.last_seen_at) as last_seen_at
from product_clusters p
left join platform_listings l on l.product_id = p.id and l.match_status = 'matched'
where p.status = 'active'
group by p.id;

-- v4.5 product-matching intelligence additions.
-- Supports product-vs-product duplicate review and safe cluster merges.
alter table review_queue add column if not exists review_type text not null default 'listing_match';
alter table review_queue add column if not exists source_product_id uuid references product_clusters(id) on delete cascade;
create index if not exists idx_review_queue_type_status on review_queue(review_type, status, created_at desc);
create index if not exists idx_review_queue_source_product on review_queue(source_product_id);
create unique index if not exists idx_review_queue_duplicate_product_open
  on review_queue(source_product_id, candidate_product_id, review_type, status)
  where review_type = 'duplicate_product'
    and status = 'needs_review'
    and source_product_id is not null
    and candidate_product_id is not null;

create table if not exists product_merge_log (
  id uuid primary key default gen_random_uuid(),
  primary_product_id uuid not null references product_clusters(id) on delete cascade,
  duplicate_product_id uuid not null references product_clusters(id) on delete cascade,
  source text not null default 'manual',
  reviewer_note text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(primary_product_id, duplicate_product_id)
);
create index if not exists idx_product_merge_log_created on product_merge_log(created_at desc);

-- v4.5.1 hardening: avoid re-suggesting duplicate pairs and speed pair status checks.
create index if not exists idx_review_queue_duplicate_product_pair_status_all
  on review_queue(review_type, source_product_id, candidate_product_id, status)
  where review_type = 'duplicate_product'
    and source_product_id is not null
    and candidate_product_id is not null;

-- v4.5.3 production optimization layer: fast search index, safer dedupe, and diagnostics.
-- This section is idempotent and can be applied on top of existing v4.5.x databases.
create extension if not exists pg_trgm;

-- Fast read-optimized search surface. API search reads this compact projection
-- instead of repeatedly scanning product_clusters + platform_listings.
create materialized view if not exists product_search_index as
with base as (
  select
    p.id as product_id,
    p.category,
    p.brand,
    p.canonical_title,
    p.title_norm,
    p.variant_key,
    p.specs,
    p.specs->>'family' as family,
    coalesce((select string_agg(upper(v), ' ') from jsonb_array_elements_text(case when jsonb_typeof(p.specs->'model_codes') = 'array' then p.specs->'model_codes' else '[]'::jsonb end) as v), '') as model_codes_text,
    coalesce((select string_agg(lower(v), ' ') from jsonb_array_elements_text(case when jsonb_typeof(p.specs->'cpu_models') = 'array' then p.specs->'cpu_models' else '[]'::jsonb end) as v), '') as cpu_models_text,
    case when (p.specs->>'ram_gb') ~ '^[0-9]+$' then (p.specs->>'ram_gb')::integer end as ram_gb,
    case when (p.specs->>'storage_gb') ~ '^[0-9]+$' then (p.specs->>'storage_gb')::integer end as storage_gb,
    case when (p.specs->>'screen_inch') ~ '^[0-9]+(\.[0-9]+)?$' then (p.specs->>'screen_inch')::numeric end as screen_inch,
    p.specs->>'cpu_series' as cpu_series,
    p.specs->>'gpu' as gpu,
    b.best_price,
    b.best_platform,
    coalesce(b.platform_count, 0) as platform_count,
    b.last_seen_at,
    coalesce((
      select count(*)::integer
      from platform_listings l
      where l.product_id = p.id and l.match_status = 'matched'
    ), 0) as offer_count,
    (
      select l.image_url
      from platform_listings l
      where l.product_id = p.id
        and l.match_status = 'matched'
        and nullif(l.image_url, '') is not null
      order by case when l.platform = b.best_platform then 0 else 1 end,
               l.current_price asc nulls last,
               l.last_seen_at desc nulls last
      limit 1
    ) as image_url,
    concat_ws(' ',
      p.canonical_title,
      p.title_norm,
      p.brand,
      p.category,
      p.specs->>'family',
      coalesce((select string_agg(upper(v), ' ') from jsonb_array_elements_text(case when jsonb_typeof(p.specs->'model_codes') = 'array' then p.specs->'model_codes' else '[]'::jsonb end) as v), ''),
      coalesce((select string_agg(lower(v), ' ') from jsonb_array_elements_text(case when jsonb_typeof(p.specs->'cpu_models') = 'array' then p.specs->'cpu_models' else '[]'::jsonb end) as v), ''),
      p.specs->>'cpu_series',
      p.specs->>'gpu',
      p.specs->>'ram_gb',
      p.specs->>'storage_gb',
      p.specs->>'screen_inch'
    ) as search_text
  from product_clusters p
  left join current_product_best_prices b on b.product_id = p.id
  where p.status = 'active'
)
select
  base.*,
  to_tsvector('english', coalesce(base.search_text, '')) as search_vector
from base
with data;

create unique index if not exists idx_product_search_index_product_id
  on product_search_index(product_id);
create index if not exists idx_product_search_index_vector
  on product_search_index using gin(search_vector);
create index if not exists idx_product_search_index_text_trgm
  on product_search_index using gin(search_text gin_trgm_ops);
create index if not exists idx_product_search_index_category_brand
  on product_search_index(category, brand);
create index if not exists idx_product_search_index_model_trgm
  on product_search_index using gin(model_codes_text gin_trgm_ops);
create index if not exists idx_product_search_index_family
  on product_search_index(category, brand, family);
create index if not exists idx_product_search_index_price
  on product_search_index(category, best_price);
create index if not exists idx_product_search_index_platform_count
  on product_search_index(platform_count desc, last_seen_at desc);

create or replace function refresh_product_search_index_safe() returns void
language plpgsql
as $$
begin
  if to_regclass('public.product_search_index') is null then
    return;
  end if;

  begin
    refresh materialized view concurrently product_search_index;
  exception
    when object_not_in_prerequisite_state or feature_not_supported then
      refresh materialized view product_search_index;
  end;
end;
$$;

-- Space/time hardening indexes for hot paths and duplicate protection.
create index if not exists idx_platform_listings_product_platform_price
  on platform_listings(product_id, platform, current_price, last_seen_at desc)
  where match_status = 'matched';
create index if not exists idx_platform_listings_platform_urlhash_active
  on platform_listings(platform, listing_url_hash)
  where listing_url_hash is not null and listing_url_hash <> '';
-- Avoid hard migration failures on legacy duplicate URLs. Use a non-unique
-- index for speed; a later cleanup migration can promote this to unique after
-- duplicate URL rows are merged or archived.
create index if not exists idx_price_obs_listing_created_desc
  on price_observations(listing_id, created_at desc);
create index if not exists idx_price_obs_product_valid_time
  on price_observations(product_id, observed_at desc)
  where validation_status = 'valid';
create index if not exists idx_scrape_runs_recent_failures
  on scrape_runs(platform, status, started_at desc)
  where status in ('failed', 'empty', 'partial');
create index if not exists idx_anomaly_events_open_recent
  on anomaly_events(severity, created_at desc)
  where status = 'open';

-- ============================================================================
-- Mayabu v5 production architecture: incremental search, variants, queue safety,
-- circuit breakers, direct URL ingestion, and maintenance observability.
-- ============================================================================

alter table product_clusters add column if not exists exact_fingerprint text;
alter table product_clusters add column if not exists family_fingerprint text;
alter table product_clusters add column if not exists last_indexed_at timestamptz;
create index if not exists idx_product_clusters_exact_fingerprint on product_clusters(exact_fingerprint) where exact_fingerprint is not null;
create index if not exists idx_product_clusters_family_fingerprint on product_clusters(family_fingerprint) where family_fingerprint is not null;

alter table platform_listings add column if not exists last_detail_enriched_at timestamptz;
alter table platform_listings add column if not exists extraction_version text;
alter table platform_listings add column if not exists content_hash text;
alter table platform_listings add column if not exists rating numeric(4,2);
alter table platform_listings add column if not exists review_count integer;
create index if not exists idx_platform_listings_detail_due
  on platform_listings(platform, last_detail_enriched_at nulls first, last_seen_at desc);

create table if not exists variant_groups (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  brand text,
  family_key text not null,
  display_name text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(category, brand, family_key)
);
create index if not exists idx_variant_groups_lookup on variant_groups(category, brand, family_key);

create table if not exists product_variant_links (
  group_id uuid not null references variant_groups(id) on delete cascade,
  product_id uuid primary key references product_clusters(id) on delete cascade,
  exact_fingerprint text,
  relation_confidence numeric(7,2) not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_product_variant_links_group on product_variant_links(group_id, relation_confidence desc);
create index if not exists idx_product_variant_links_exact on product_variant_links(exact_fingerprint) where exact_fingerprint is not null;

-- Incremental, write-maintained search documents. This replaces the expensive
-- full materialized-view refresh on normal ingest paths while keeping the old
-- view as a compatibility fallback.
create table if not exists product_search_documents (
  product_id uuid primary key references product_clusters(id) on delete cascade,
  brand text,
  category text not null,
  canonical_title text not null,
  title_norm text,
  specs jsonb not null default '{}'::jsonb,
  family text,
  model_codes_text text not null default '',
  cpu_models_text text not null default '',
  cpu_series text,
  gpu text,
  ram_gb integer,
  storage_gb integer,
  screen_inch numeric(5,2),
  best_price numeric(12,2),
  best_platform text,
  platform_count integer not null default 0,
  offer_count integer not null default 0,
  image_url text,
  last_seen_at timestamptz,
  variant_group_id uuid references variant_groups(id) on delete set null,
  exact_fingerprint text,
  family_fingerprint text,
  search_text text not null default '',
  search_vector tsvector not null,
  indexed_at timestamptz not null default now()
);
create index if not exists idx_search_docs_vector on product_search_documents using gin(search_vector);
create index if not exists idx_search_docs_trgm on product_search_documents using gin(search_text gin_trgm_ops);
create index if not exists idx_search_docs_search_text_lower_trgm on product_search_documents using gin(lower(search_text) gin_trgm_ops);
create index if not exists idx_search_docs_model_trgm on product_search_documents using gin(model_codes_text gin_trgm_ops);
create index if not exists idx_search_docs_model_lower_trgm on product_search_documents using gin(lower(model_codes_text) gin_trgm_ops);
create index if not exists idx_search_docs_category_brand on product_search_documents(category, brand);
create index if not exists idx_search_docs_family on product_search_documents(category, brand, family);
create index if not exists idx_search_docs_variant_group on product_search_documents(variant_group_id);
create index if not exists idx_search_docs_price on product_search_documents(category, best_price) where best_price is not null;
create index if not exists idx_search_docs_platform_freshness on product_search_documents(platform_count desc, last_seen_at desc);

create table if not exists search_document_dirty (
  product_id uuid primary key references product_clusters(id) on delete cascade,
  reason text not null default 'unknown',
  dirty_at timestamptz not null default now(),
  attempts integer not null default 0,
  last_error text
);
alter table search_document_dirty add column if not exists claimed_at timestamptz;
alter table search_document_dirty add column if not exists claimed_by text;
create index if not exists idx_search_document_dirty_order on search_document_dirty(dirty_at asc);
create index if not exists idx_search_document_dirty_claim on search_document_dirty(claimed_at, dirty_at asc);

create or replace function mark_search_document_dirty(p_product_id uuid, p_reason text default 'update') returns void
language plpgsql
as $$
begin
  if p_product_id is null then
    return;
  end if;
  insert into search_document_dirty(product_id, reason, dirty_at, attempts, last_error)
  values (p_product_id, coalesce(p_reason, 'update'), now(), 0, null)
  on conflict (product_id) do update set
    reason = excluded.reason,
    dirty_at = excluded.dirty_at,
    claimed_at = null,
    claimed_by = null,
    last_error = null;
end;
$$;

create or replace function refresh_product_search_document(p_product_id uuid) returns void
language plpgsql
as $$
begin
  if not exists (select 1 from product_clusters where id = p_product_id and status = 'active') then
    delete from product_search_documents where product_id = p_product_id;
    delete from search_document_dirty where product_id = p_product_id;
    return;
  end if;

  insert into product_search_documents(
    product_id, brand, category, canonical_title, title_norm, specs, family,
    model_codes_text, cpu_models_text, cpu_series, gpu, ram_gb, storage_gb,
    screen_inch, best_price, best_platform, platform_count, offer_count,
    image_url, last_seen_at, variant_group_id, exact_fingerprint,
    family_fingerprint, search_text, search_vector, indexed_at
  )
  select
    p.id,
    p.brand,
    p.category,
    p.canonical_title,
    p.title_norm,
    p.specs,
    p.specs->>'family',
    coalesce((select string_agg(upper(mc.value), ' ') from jsonb_array_elements_text(
      case when jsonb_typeof(p.specs->'model_codes') = 'array' then p.specs->'model_codes' else '[]'::jsonb end
    ) as mc(value)), ''),
    coalesce((select string_agg(lower(cm.value), ' ') from jsonb_array_elements_text(
      case when jsonb_typeof(p.specs->'cpu_models') = 'array' then p.specs->'cpu_models' else '[]'::jsonb end
    ) as cm(value)), ''),
    p.specs->>'cpu_series',
    p.specs->>'gpu',
    case when (p.specs->>'ram_gb') ~ '^[0-9]+$' then (p.specs->>'ram_gb')::integer end,
    case when (p.specs->>'storage_gb') ~ '^[0-9]+$' then (p.specs->>'storage_gb')::integer end,
    case when (p.specs->>'screen_inch') ~ '^[0-9]+(\.[0-9]+)?$' then (p.specs->>'screen_inch')::numeric end,
    (
      select coalesce(
        min(l.current_price) filter (where l.stock_status <> 'out_of_stock'),
        min(l.current_price)
      )
      from platform_listings l
      where l.product_id = p.id
        and mayabu_listing_is_public_priced(
          l.platform, p.category, l.match_status, l.current_price, l.currency
        )
    ),
    (
      select l.platform
      from platform_listings l
      where l.product_id = p.id
        and mayabu_listing_is_public_priced(
          l.platform, p.category, l.match_status, l.current_price, l.currency
        )
        and (
          l.stock_status <> 'out_of_stock'
          or not exists (
            select 1 from platform_listings x
            where x.product_id = p.id
              and mayabu_listing_is_public_priced(
                x.platform, p.category, x.match_status, x.current_price, x.currency
              )
              and x.stock_status <> 'out_of_stock'
          )
        )
      order by l.current_price asc, l.last_seen_at desc
      limit 1
    ),
    (
      select count(distinct l.platform)::integer
      from platform_listings l
      where l.product_id = p.id
        and mayabu_listing_is_public_priced(
          l.platform, p.category, l.match_status, l.current_price, l.currency
        )
    ),
    (
      select count(*)::integer from platform_listings l
      where l.product_id = p.id and l.match_status = 'matched'
        and mayabu_listing_is_public_offer(l.platform, p.category)
    ),
    (
      select l.image_url from platform_listings l
      where l.product_id = p.id and l.match_status = 'matched' and nullif(l.image_url, '') is not null
      order by (l.current_price is null), l.current_price asc nulls last, l.last_seen_at desc
      limit 1
    ),
    (select max(l.last_seen_at) from platform_listings l where l.product_id = p.id),
    pvl.group_id,
    coalesce(p.exact_fingerprint, pvl.exact_fingerprint),
    p.family_fingerprint,
    concat_ws(' ', p.canonical_title, p.title_norm, p.brand, p.category,
      p.specs->>'family',
      coalesce((select string_agg(upper(v), ' ') from jsonb_array_elements_text(
        case when jsonb_typeof(p.specs->'model_codes') = 'array' then p.specs->'model_codes' else '[]'::jsonb end
      ) v), ''),
      coalesce((select string_agg(lower(v), ' ') from jsonb_array_elements_text(
        case when jsonb_typeof(p.specs->'cpu_models') = 'array' then p.specs->'cpu_models' else '[]'::jsonb end
      ) v), ''),
      p.specs->>'cpu_series', p.specs->>'gpu', p.specs->>'ram_gb',
      p.specs->>'storage_gb', p.specs->>'screen_inch'
    ),
    to_tsvector('english', concat_ws(' ', p.canonical_title, p.title_norm, p.brand,
      p.category, p.specs->>'family', p.specs->>'cpu_series', p.specs->>'gpu',
      p.specs->>'ram_gb', p.specs->>'storage_gb', p.specs->>'screen_inch')),
    now()
  from product_clusters p
  left join product_variant_links pvl on pvl.product_id = p.id
  where p.id = p_product_id and p.status = 'active'
  on conflict (product_id) do update set
    brand = excluded.brand,
    category = excluded.category,
    canonical_title = excluded.canonical_title,
    title_norm = excluded.title_norm,
    specs = excluded.specs,
    family = excluded.family,
    model_codes_text = excluded.model_codes_text,
    cpu_models_text = excluded.cpu_models_text,
    cpu_series = excluded.cpu_series,
    gpu = excluded.gpu,
    ram_gb = excluded.ram_gb,
    storage_gb = excluded.storage_gb,
    screen_inch = excluded.screen_inch,
    best_price = excluded.best_price,
    best_platform = excluded.best_platform,
    platform_count = excluded.platform_count,
    offer_count = excluded.offer_count,
    image_url = excluded.image_url,
    last_seen_at = excluded.last_seen_at,
    variant_group_id = excluded.variant_group_id,
    exact_fingerprint = excluded.exact_fingerprint,
    family_fingerprint = excluded.family_fingerprint,
    search_text = excluded.search_text,
    search_vector = excluded.search_vector,
    indexed_at = excluded.indexed_at;

  update product_clusters set last_indexed_at = now() where id = p_product_id;
  delete from search_document_dirty where product_id = p_product_id;
end;
$$;

create or replace function trg_product_search_dirty() returns trigger
language plpgsql
as $$
begin
  perform mark_search_document_dirty(coalesce(new.id, old.id), tg_op || ':product');
  return coalesce(new, old);
end;
$$;

drop trigger if exists product_clusters_search_dirty on product_clusters;
create trigger product_clusters_search_dirty
after insert or update of canonical_title, title_norm, brand, category, specs, status, exact_fingerprint, family_fingerprint
on product_clusters for each row execute function trg_product_search_dirty();

create or replace function trg_listing_search_dirty() returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    perform mark_search_document_dirty(old.product_id, 'delete:listing');
    return old;
  end if;
  perform mark_search_document_dirty(new.product_id, tg_op || ':listing');
  if tg_op = 'UPDATE' and old.product_id is distinct from new.product_id then
    perform mark_search_document_dirty(old.product_id, 'move:listing');
  end if;
  return new;
end;
$$;

drop trigger if exists platform_listings_search_dirty on platform_listings;
create trigger platform_listings_search_dirty
after insert or delete or update of product_id, title, current_price, current_mrp, stock_status, image_url, match_status, last_seen_at
on platform_listings for each row execute function trg_listing_search_dirty();

-- Queue idempotency and lease metadata.
alter table scrape_tasks add column if not exists idempotency_key text;
alter table scrape_tasks add column if not exists lease_expires_at timestamptz;
alter table scrape_tasks add column if not exists result jsonb not null default '{}'::jsonb;
alter table scrape_tasks add column if not exists created_by text not null default 'system';
alter table scrape_tasks drop constraint if exists scrape_tasks_task_type_check;
alter table scrape_tasks add constraint scrape_tasks_task_type_check check (
  task_type in ('discovery','discovery_search','refresh_listing','refresh_hot_product',
                'retry_failed','enrichment','enrich_listing','targeted_discovery','diagnostic',
                'direct_ingest','index_product','maintenance','verify_listing')
);
alter table scrape_tasks drop constraint if exists scrape_tasks_status_check;
alter table scrape_tasks add constraint scrape_tasks_status_check check (
  status in ('pending','running','completed','failed','dead','cancelled','paused')
);
alter table scrape_tasks drop constraint if exists scrape_tasks_platform_check;
alter table scrape_tasks add constraint scrape_tasks_platform_check check (
  platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics','system')
);
create unique index if not exists idx_scrape_tasks_idempotency_active
  on scrape_tasks(idempotency_key)
  where idempotency_key is not null and status in ('pending','running','paused');
create index if not exists idx_scrape_tasks_lease on scrape_tasks(status, lease_expires_at)
  where status = 'running';

alter table platform_health add column if not exists consecutive_failures integer not null default 0;
alter table platform_health add column if not exists success_count bigint not null default 0;
alter table platform_health add column if not exists failure_count bigint not null default 0;
alter table platform_health add column if not exists circuit_open_until timestamptz;
alter table platform_health add column if not exists last_latency_ms integer;
alter table platform_health add column if not exists last_error_code text;
create index if not exists idx_platform_health_circuit on platform_health(circuit_open_until) where circuit_open_until is not null;

create table if not exists maintenance_runs (
  id uuid primary key default gen_random_uuid(),
  job_name text not null,
  status text not null check (status in ('running','completed','failed','partial')),
  stats jsonb not null default '{}'::jsonb,
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);
create index if not exists idx_maintenance_runs_recent on maintenance_runs(job_name, started_at desc);

-- Seed all existing active products for one-time incremental backfill.
insert into search_document_dirty(product_id, reason)
select id, 'v5_backfill' from product_clusters where status = 'active'
on conflict (product_id) do nothing;

-- Mayabu v5.1 privileged-action audit trail.
create table if not exists admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  action text not null,
  actor_hash text,
  target_type text,
  target_id text,
  request_id text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_admin_audit_log_created on admin_audit_log(created_at desc);
create index if not exists idx_admin_audit_log_target on admin_audit_log(target_type, target_id, created_at desc);

-- Mayabu v5.2 efficient live price verification.
alter table platform_listings add column if not exists last_verification_attempt_at timestamptz;
alter table platform_listings add column if not exists last_verified_at timestamptz;
alter table platform_listings add column if not exists verification_status text not null default 'never';
alter table platform_listings add column if not exists verification_source text;
alter table platform_listings add column if not exists next_allowed_verification_at timestamptz;
alter table platform_listings add column if not exists consecutive_verification_failures integer not null default 0;
alter table platform_listings drop constraint if exists platform_listings_verification_status_check;
alter table platform_listings add constraint platform_listings_verification_status_check check (
  verification_status in ('never','pending','verified','failed','blocked','unavailable','out_of_stock')
);
create index if not exists idx_platform_listings_verification_due
  on platform_listings(next_allowed_verification_at, refresh_priority, last_verified_at)
  where match_status = 'matched';
create index if not exists idx_platform_listings_product_verification
  on platform_listings(product_id, last_verified_at desc, verification_status)
  where match_status = 'matched';

alter table scrape_tasks add column if not exists request_count integer not null default 1;
alter table scrape_tasks drop constraint if exists scrape_tasks_task_type_check;
alter table scrape_tasks add constraint scrape_tasks_task_type_check check (
  task_type in ('discovery','discovery_search','refresh_listing','refresh_hot_product',
                'retry_failed','enrichment','enrich_listing','targeted_discovery','diagnostic',
                'direct_ingest','index_product','maintenance','verify_listing')
);
create index if not exists idx_scrape_tasks_live_verification_active
  on scrape_tasks(status, priority, scheduled_at, created_at)
  where task_type = 'verify_listing' and status in ('pending','running','paused');

create table if not exists live_verification_events (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references scrape_tasks(id) on delete set null,
  product_id uuid references product_clusters(id) on delete set null,
  listing_id uuid references platform_listings(id) on delete set null,
  platform text not null,
  status text not null check (status in ('started','verified','failed','blocked','cooldown','busy')),
  request_count integer not null default 1,
  source text,
  old_price numeric(12,2),
  verified_price numeric(12,2),
  stock_status text,
  duration_ms integer,
  error_code text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_live_verification_events_product_time
  on live_verification_events(product_id, created_at desc);
create index if not exists idx_live_verification_events_platform_time
  on live_verification_events(platform, created_at desc);
create index if not exists idx_live_verification_events_created_at
  on live_verification_events(created_at);


-- ============================================================
-- Platform registry + scalable daily platform prices (v5.6)
-- Idempotent upgrades for existing databases.
-- ============================================================

create table if not exists platform_registry (
  slug text primary key,
  display_name text not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

insert into platform_registry(slug, display_name) values
  ('amazon', 'Amazon India'),
  ('flipkart', 'Flipkart'),
  ('croma', 'Croma'),
  ('reliancedigital', 'Reliance Digital'),
  ('vijaysales', 'Vijay Sales'),
  ('jiomart', 'JioMart'),
  ('poorvika', 'Poorvika'),
  ('bajajelectronics', 'Bajaj Electronics')
on conflict (slug) do update set display_name = excluded.display_name;

create table if not exists daily_product_platform_prices (
  product_id uuid not null references product_clusters(id) on delete cascade,
  date date not null,
  platform text not null,
  min_price numeric(12,2),
  max_price numeric(12,2),
  observations_count integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (product_id, date, platform),
  constraint daily_product_platform_prices_platform_fk
    foreign key (platform) references platform_registry(slug)
);

create index if not exists idx_daily_product_platform_prices_date
  on daily_product_platform_prices(date desc, platform);
create index if not exists idx_daily_product_platform_prices_product
  on daily_product_platform_prices(product_id, date desc);

alter table platform_listings drop constraint if exists platform_listings_platform_check;
alter table platform_listings add constraint platform_listings_platform_check check (
  platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')
);

alter table scrape_budget drop constraint if exists scrape_budget_platform_check;
alter table scrape_budget add constraint scrape_budget_platform_check check (
  platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')
);

alter table platform_health drop constraint if exists platform_health_platform_check;
alter table platform_health add constraint platform_health_platform_check check (
  platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')
);

alter table scheduler_plans drop constraint if exists scheduler_plans_platform_check;
alter table scheduler_plans add constraint scheduler_plans_platform_check check (
  platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics')
);

alter table scrape_tasks drop constraint if exists scrape_tasks_platform_check;
alter table scrape_tasks add constraint scrape_tasks_platform_check check (
  platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','jiomart','poorvika','bajajelectronics','system')
);

insert into platform_health(platform)
values ('vijaysales'), ('jiomart'), ('poorvika'), ('bajajelectronics')
on conflict (platform) do nothing;

insert into schema_migrations(version) values ('2026_09_platform_registry_v1')
on conflict (version) do nothing;

-- Aggregate product engagement for homepage Trending / Popular (no personal profiles).
create table if not exists product_activity_hourly (
  product_id uuid not null references product_clusters(id) on delete cascade,
  event_type text not null,
  hour_bucket timestamptz not null,
  event_count integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (product_id, event_type, hour_bucket),
  constraint product_activity_hourly_event_check check (
    event_type in ('product_view', 'search_click', 'retailer_click')
  ),
  constraint product_activity_hourly_count_check check (event_count >= 0)
);

create index if not exists idx_product_activity_hourly_bucket
  on product_activity_hourly(hour_bucket desc, event_type);

create table if not exists product_activity_dedupe (
  client_hash text not null,
  product_id uuid not null references product_clusters(id) on delete cascade,
  event_type text not null,
  hour_bucket timestamptz not null,
  created_at timestamptz not null default now(),
  primary key (client_hash, product_id, event_type, hour_bucket)
);

insert into schema_migrations(version) values ('2026_03_product_activity_v1')
on conflict (version) do nothing;

-- NOTE (platform authority):
-- Runtime validation uses mayabu.platforms.registry.
-- product_search_documents already stores category + specs JSONB, so non-laptop
-- products can be indexed without adding ram_gb/tv_size/... as top-level SQL columns.
-- Public search remains laptop-gated in query_parser until the dedicated search task.
-- See mayabu/search/index_readiness.py for blockers and next changes.
-- CHECK constraints on listing/task tables remain as a defense-in-depth allowlist
-- synchronized with the eight current retailers. Prefer extending platform_registry
-- + application registry together; avoid adding per-retailer price columns.
-- Follow-up: migrate remaining platform CHECKs to FK against platform_registry
-- once scrape_tasks 'system' sentinel is modeled cleanly.
-- Account System V1: users, sessions, email verification, password reset, wishlist.
-- Idempotent / safe to re-apply.

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  normalized_email text not null,
  password_hash text not null,
  display_name text,
  email_verified_at timestamptz,
  status text not null default 'active'
    check (status in ('active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_login_at timestamptz
);

create unique index if not exists idx_users_normalized_email
  on users (normalized_email);
create unique index if not exists idx_users_email
  on users (email);

create table if not exists user_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  user_agent text
);

create unique index if not exists idx_user_sessions_token_hash
  on user_sessions (token_hash);
create index if not exists idx_user_sessions_user_id
  on user_sessions (user_id);
create index if not exists idx_user_sessions_expires
  on user_sessions (expires_at)
  where revoked_at is null;

create table if not exists email_verification_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used_at timestamptz
);

create unique index if not exists idx_email_verification_token_hash
  on email_verification_tokens (token_hash);
create index if not exists idx_email_verification_user
  on email_verification_tokens (user_id, created_at desc);

create table if not exists password_reset_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used_at timestamptz
);

create unique index if not exists idx_password_reset_token_hash
  on password_reset_tokens (token_hash);
create index if not exists idx_password_reset_user
  on password_reset_tokens (user_id, created_at desc);

create table if not exists user_wishlist (
  user_id uuid not null references users(id) on delete cascade,
  product_id uuid not null references product_clusters(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, product_id)
);

create index if not exists idx_user_wishlist_user_created
  on user_wishlist (user_id, created_at desc);
create index if not exists idx_user_wishlist_product
  on user_wishlist (product_id);

alter table user_wishlist
  add column if not exists target_price numeric(12,2),
  add column if not exists notify_on_drop boolean not null default false,
  add column if not exists last_notified_price numeric(12,2),
  add column if not exists last_notified_at timestamptz,
  add column if not exists updated_at timestamptz not null default now();

create index if not exists idx_user_wishlist_watch
  on user_wishlist (product_id)
  where notify_on_drop = true or target_price is not null;

create table if not exists scheduler_heartbeats (
  domain text primary key,
  holder_id text not null,
  leased_until timestamptz not null,
  heartbeat_at timestamptz not null default now(),
  last_successful_tick_at timestamptz,
  jobs_scheduled_total bigint not null default 0,
  last_error text,
  last_tick_result text,
  last_tick_duration_ms integer,
  last_tick_jobs integer,
  updated_at timestamptz not null default now()
);

create index if not exists idx_platform_listings_due_refresh_v2
  on platform_listings (platform, last_successful_refresh_at, refresh_priority)
  where listing_url is not null
    and match_status in ('matched', 'unmatched', 'needs_review');

insert into schema_migrations(version) values ('2026_09_20_account_system_v1')
on conflict (version) do nothing;
insert into schema_migrations(version) values ('2026_09_21_price_engine_v1')
on conflict (version) do nothing;
insert into schema_migrations(version) values ('2026_09_21_scheduler_tick_duration')
on conflict (version) do nothing;
