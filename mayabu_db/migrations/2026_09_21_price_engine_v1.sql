-- Price Intelligence Engine V1: scheduler lease/heartbeat, price-watch
-- foundation, and due-listing index. Scheduler correctness is database-backed
-- (survives Redis restart). Notifications are stored only — delivery is deferred.

create table if not exists scheduler_heartbeats (
  domain text primary key,
  holder_id text not null,
  leased_until timestamptz not null,
  heartbeat_at timestamptz not null default now(),
  last_successful_tick_at timestamptz,
  jobs_scheduled_total bigint not null default 0,
  last_error text,
  last_tick_result text,
  updated_at timestamptz not null default now()
);

alter table user_wishlist
  add column if not exists target_price numeric(12,2),
  add column if not exists notify_on_drop boolean not null default false,
  add column if not exists last_notified_price numeric(12,2),
  add column if not exists last_notified_at timestamptz,
  add column if not exists updated_at timestamptz not null default now();

create index if not exists idx_user_wishlist_watch
  on user_wishlist (product_id)
  where notify_on_drop = true or target_price is not null;

-- Due-refresh path: eligible listings ordered by last success / platform.
create index if not exists idx_platform_listings_due_refresh_v2
  on platform_listings (platform, last_successful_refresh_at, refresh_priority)
  where listing_url is not null
    and match_status in ('matched', 'unmatched', 'needs_review');

insert into schema_migrations(version)
values ('2026_09_21_price_engine_v1')
on conflict (version) do nothing;
