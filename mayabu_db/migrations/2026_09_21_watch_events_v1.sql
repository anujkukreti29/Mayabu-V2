-- Watchlist event stream for returning-user Price Watch Dashboard.
-- Idempotent via fingerprint. Delivery (email/push) remains deferred.

create table if not exists watch_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  product_id uuid not null references product_clusters(id) on delete cascade,
  event_type text not null
    check (event_type in (
      'price_drop',
      'target_reached',
      'back_in_stock',
      'out_of_stock',
      'new_tracked_low'
    )),
  fingerprint text not null,
  current_price numeric(12,2),
  previous_price numeric(12,2),
  target_price numeric(12,2),
  stock_status text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  seen_at timestamptz
);

create unique index if not exists uq_watch_events_fingerprint
  on watch_events (fingerprint);

create index if not exists idx_watch_events_user_created
  on watch_events (user_id, created_at desc);

create index if not exists idx_watch_events_user_unseen
  on watch_events (user_id, created_at desc)
  where seen_at is null;

create index if not exists idx_watch_events_product
  on watch_events (product_id, created_at desc);
