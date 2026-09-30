from mayabu_db.connection import close_connection_pool, db_connection
from mayabu.search.cache import get_cache
from mayabu.search.index_manager import refresh_product_search_documents

SQL = """
select d.product_id::text as product_id,
       p.canonical_title,
       d.best_price as doc_price,
       b.best_price as view_price
from product_search_documents d
join product_clusters p on p.id = d.product_id
join current_product_best_prices b on b.product_id = d.product_id
where d.best_price is distinct from b.best_price
"""


def main() -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = list(cur.fetchall())
    print("stale_docs", len(rows))
    for row in rows:
        print(dict(row))
    ids = [row["product_id"] for row in rows]
    if ids:
        print(refresh_product_search_documents(ids, strict=True))
        cache = get_cache()
        deleted = sum(cache.invalidate_product(pid) for pid in ids)
        print("cache_invalidated_keys", deleted)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        leftover = list(cur.fetchall())
    print("stale_after", len(leftover))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_connection_pool(timeout=1.0)
