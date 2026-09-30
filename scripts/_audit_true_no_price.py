from mayabu_db.connection import close_connection_pool, db_connection

SQL = """
select p.id::text, p.category, p.canonical_title, b.best_price
from product_clusters p
join current_product_best_prices b on b.product_id = p.id
where p.status = 'active'
  and b.best_price is null
  and not exists (
    select 1 from platform_listings l
    where l.product_id = p.id
      and mayabu_listing_is_public_priced(
        l.platform, p.category, l.match_status, l.current_price, l.currency
      )
  )
order by p.category
limit 5
"""


def main() -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = list(cur.fetchall())
    print("true_no_price", len(rows))
    for row in rows:
        print(dict(row))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_connection_pool(timeout=1.0)
