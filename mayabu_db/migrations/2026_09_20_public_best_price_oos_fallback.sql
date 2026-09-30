-- Public best-price must not be null when a matched public offer still has
-- a valid current_price > 0. Prefer in-stock; fall back to priced out_of_stock
-- last-known prices (verification preserves those instead of erasing them).

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

insert into search_document_dirty(product_id, reason, dirty_at, attempts, last_error)
select d.product_id, 'best_price_oos_fallback', now(), 0, null
from product_search_documents d
join current_product_best_prices b on b.product_id = d.product_id
where d.best_price is distinct from b.best_price
on conflict (product_id) do update set
  reason = excluded.reason,
  dirty_at = excluded.dirty_at,
  claimed_at = null,
  claimed_by = null,
  last_error = null;
