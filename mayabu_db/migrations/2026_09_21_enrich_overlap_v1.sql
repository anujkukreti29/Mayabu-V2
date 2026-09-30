-- Enrichment + targeted overlap discovery task types and attempt cooldown.

alter table scrape_tasks drop constraint if exists scrape_tasks_task_type_check;
alter table scrape_tasks add constraint scrape_tasks_task_type_check check (
  task_type in (
    'discovery','discovery_search','refresh_listing','refresh_hot_product',
    'retry_failed','enrichment','enrich_listing','targeted_discovery','diagnostic',
    'direct_ingest','index_product','maintenance','verify_listing'
  )
);

alter table scheduler_plans drop constraint if exists scheduler_plans_task_type_check;
alter table scheduler_plans add constraint scheduler_plans_task_type_check check (
  task_type in (
    'discovery','discovery_search','refresh_listing','refresh_hot_product',
    'retry_failed','enrichment','enrich_listing','targeted_discovery','diagnostic',
    'direct_ingest','index_product','maintenance','verify_listing'
  )
);

create table if not exists overlap_discovery_attempts (
  product_id uuid not null references product_clusters(id) on delete cascade,
  target_platform text not null,
  query_fingerprint text not null,
  last_attempted_at timestamptz not null default now(),
  last_result text,
  candidates_found integer not null default 0,
  exact_matches integer not null default 0,
  primary key (product_id, target_platform, query_fingerprint)
);

create index if not exists idx_overlap_attempts_recent
  on overlap_discovery_attempts(last_attempted_at desc);

create index if not exists idx_listings_enrich_due
  on platform_listings(last_detail_enriched_at nulls first, updated_at desc)
  where match_status = 'matched' and listing_url is not null;
