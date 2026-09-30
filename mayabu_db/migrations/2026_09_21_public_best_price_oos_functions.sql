-- Ensure public best-price SQL matches Python OOS last-known fallback.
-- Safe to re-apply. Does not rewrite search-document refresh bodies.

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

insert into schema_migrations(version)
values ('2026_09_21_public_best_price_oos_functions')
on conflict (version) do nothing;
