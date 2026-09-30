-- Public offer semantics: offer_count == unique retailer (platform) count.
-- Listing row inflation must not appear as “N stores” in search documents.

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
      select min(l.current_price)
      from platform_listings l
      where l.product_id = p.id and l.match_status = 'matched'
        and l.current_price is not null and l.current_price > 0
        and l.stock_status <> 'out_of_stock'
        and coalesce(l.currency, 'INR') = 'INR'
        and mayabu_listing_is_public_offer(l.platform, p.category)
    ),
    (
      select l.platform
      from platform_listings l
      where l.product_id = p.id and l.match_status = 'matched'
        and l.current_price is not null and l.current_price > 0
        and l.stock_status <> 'out_of_stock'
        and coalesce(l.currency, 'INR') = 'INR'
        and mayabu_listing_is_public_offer(l.platform, p.category)
      order by l.current_price asc, l.last_seen_at desc
      limit 1
    ),
    (
      select count(distinct l.platform)::integer
      from platform_listings l
      where l.product_id = p.id and l.match_status = 'matched'
        and l.current_price is not null and l.current_price > 0
        and coalesce(l.currency, 'INR') = 'INR'
        and mayabu_listing_is_public_offer(l.platform, p.category)
    ),
    -- Public offer_count mirrors unique retailers (platform_count).
    (
      select count(distinct l.platform)::integer
      from platform_listings l
      where l.product_id = p.id and l.match_status = 'matched'
        and l.current_price is not null and l.current_price > 0
        and coalesce(l.currency, 'INR') = 'INR'
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

-- Align existing search documents without waiting for dirty refresh.
update product_search_documents d
set offer_count = coalesce(d.platform_count, 0),
    indexed_at = now()
where coalesce(d.offer_count, 0) is distinct from coalesce(d.platform_count, 0);
