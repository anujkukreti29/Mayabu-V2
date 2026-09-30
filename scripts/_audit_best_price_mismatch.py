"""Bounded local audit: eligible priced public offers vs current_product_best_prices."""

from __future__ import annotations

from mayabu_db.connection import close_connection_pool, db_connection


SUMMARY_SQL = """
with elig as (
  select
    p.id as product_id,
    p.category,
    l.platform,
    l.current_price,
    l.stock_status,
    l.currency
  from product_clusters p
  join platform_listings l on l.product_id = p.id
  where p.status = 'active'
    and l.match_status = 'matched'
    and l.current_price is not null
    and l.current_price > 0
    and coalesce(l.currency, 'INR') = 'INR'
    and mayabu_listing_is_public_offer(l.platform, p.category)
),
mins as (
  select
    product_id,
    category,
    min(current_price) as min_any_priced,
    min(current_price) filter (
      where coalesce(stock_status, '') <> 'out_of_stock'
    ) as min_in_stock,
    count(*) as priced_public,
    count(*) filter (where coalesce(stock_status, '') = 'out_of_stock') as oos_priced,
    count(*) filter (where coalesce(stock_status, '') <> 'out_of_stock') as instock_priced
  from elig
  group by product_id, category
)
select
  (select count(*) from mins) as products_with_priced_public,
  (select count(*) from current_product_best_prices b
     join mins m on m.product_id = b.product_id
    where b.best_price is null) as view_null_with_any_priced,
  (select count(*) from current_product_best_prices b
     join mins m on m.product_id = b.product_id
    where b.best_price is null and m.instock_priced > 0) as view_null_with_instock,
  (select count(*) from current_product_best_prices b
     join mins m on m.product_id = b.product_id
    where b.best_price is null and m.instock_priced = 0 and m.oos_priced > 0
  ) as view_null_oos_only,
  (select count(*) from current_product_best_prices b
     join mins m on m.product_id = b.product_id
    where b.best_price is distinct from m.min_any_priced) as view_ne_min_any,
  (select count(*) from current_product_best_prices b
     join mins m on m.product_id = b.product_id
    where b.best_price is distinct from m.min_in_stock) as view_ne_min_instock,
  (select count(*) from product_search_documents d
     join mins m on m.product_id = d.product_id
    where d.best_price is null) as docs_null_with_any_priced;
"""

EXAMPLES_SQL = """
select p.id, p.category, p.canonical_title, b.best_price, b.best_platform, b.platform_count
from product_clusters p
join current_product_best_prices b on b.product_id = p.id
where p.status = 'active'
  and b.best_price is null
  and exists (
    select 1 from platform_listings l
    where l.product_id = p.id
      and l.match_status = 'matched'
      and l.current_price is not null
      and l.current_price > 0
      and coalesce(l.currency, 'INR') = 'INR'
      and mayabu_listing_is_public_offer(l.platform, p.category)
  )
order by p.category, p.canonical_title
limit 8
"""

OFFERS_SQL = """
select platform, current_price, stock_status, currency, match_status
from platform_listings
where product_id = %s and match_status = 'matched'
order by current_price asc nulls last
"""


def main() -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(SUMMARY_SQL)
        print("SUMMARY", dict(cur.fetchone()))
        cur.execute(EXAMPLES_SQL)
        rows = list(cur.fetchall())
        print("EXAMPLES", len(rows))
        for row in rows:
            print({k: row[k] for k in row.keys()})
            cur.execute(OFFERS_SQL, (row["id"],))
            for offer in cur.fetchall():
                print("  offer", dict(offer))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_connection_pool(timeout=1.0)
