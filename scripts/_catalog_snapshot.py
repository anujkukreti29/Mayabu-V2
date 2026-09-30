"""Quick catalog snapshot for local/staging qualification."""
from __future__ import annotations

from mayabu.search.index_manager import backfill_product_search_documents, get_search_index_stats
from mayabu_db.connection import db_connection


def main() -> None:
    print("backfill", backfill_product_search_documents(batch_size=500))
    print("index_status", get_search_index_stats())
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT category, COUNT(*) FROM product_clusters "
                "WHERE status = 'active' GROUP BY 1 ORDER BY 1"
            )
            print("products", cur.fetchall())
            cur.execute("SELECT category, COUNT(*) FROM platform_listings GROUP BY 1 ORDER BY 1")
            print("listings", cur.fetchall())
            cur.execute(
                "SELECT COUNT(*) FROM platform_listings "
                "WHERE category = 'unknown' OR category IS NULL"
            )
            print("unknown_listings", cur.fetchone())
            cur.execute(
                "SELECT category, COUNT(*) FROM product_search_documents GROUP BY 1 ORDER BY 1"
            )
            print("search_docs", cur.fetchall())
            cur.execute("SELECT COUNT(*) FROM search_document_dirty")
            print("dirty_rows", cur.fetchone())
            cur.execute(
                """
                SELECT p.category,
                       COUNT(*) FILTER (WHERE offer_cnt = 1) AS one_offer,
                       COUNT(*) FILTER (WHERE offer_cnt > 1) AS multi,
                       ROUND(AVG(offer_cnt)::numeric, 2) AS avg_offers
                FROM (
                  SELECT product_id, COUNT(*) AS offer_cnt
                  FROM platform_listings
                  WHERE product_id IS NOT NULL AND match_status = 'matched'
                  GROUP BY product_id
                ) o
                JOIN product_clusters p ON p.id = o.product_id
                GROUP BY p.category
                ORDER BY 1
                """
            )
            print("offer_dist", cur.fetchall())
            cur.execute(
                """
                SELECT category, platform, COUNT(*)
                FROM platform_listings
                GROUP BY 1, 2
                ORDER BY 1, 2
                """
            )
            print("platform_cat", cur.fetchall())


if __name__ == "__main__":
    main()
