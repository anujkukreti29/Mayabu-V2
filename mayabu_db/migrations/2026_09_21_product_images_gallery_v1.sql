-- Product image gallery (normalized). Primary image remains on search docs / listings.
create table if not exists product_images (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references product_clusters(id) on delete cascade,
  listing_id uuid references platform_listings(id) on delete set null,
  image_url text not null,
  url_hash text not null,
  source_platform text,
  source_position integer not null default 0,
  image_role text not null default 'gallery'
    check (image_role in ('primary','gallery','variant','unknown')),
  width integer,
  height integer,
  is_primary boolean not null default false,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  unique (product_id, url_hash)
);

create index if not exists idx_product_images_product_active
  on product_images(product_id, is_primary desc, source_position asc)
  where active = true;

create index if not exists idx_product_images_listing
  on product_images(listing_id)
  where listing_id is not null;
