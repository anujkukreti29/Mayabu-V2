-- Platform-day price rollup used by Price Intelligence and history charts.
-- Create without a platform_registry FK so incomplete local catalogs can ingest.

create table if not exists daily_product_platform_prices (
  product_id uuid not null references product_clusters(id) on delete cascade,
  date date not null,
  platform text not null,
  min_price numeric(12,2),
  max_price numeric(12,2),
  observations_count integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (product_id, date, platform)
);

create index if not exists idx_daily_product_platform_prices_date
  on daily_product_platform_prices(date desc, platform);
create index if not exists idx_daily_product_platform_prices_product
  on daily_product_platform_prices(product_id, date desc);

insert into schema_migrations(version)
values ('2026_09_21_daily_product_platform_prices')
on conflict (version) do nothing;
