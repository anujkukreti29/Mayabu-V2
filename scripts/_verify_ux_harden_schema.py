"""Verify required Smart Commerce / auth schema on test DB."""
from __future__ import annotations

import os
import sys

import psycopg

URL = os.environ.get("MAYABU_TEST_DATABASE_URL") or os.environ["DATABASE_URL"]

REQUIRED = [
    "users",
    "user_wishlist",
    "search_queries",
    "product_search_documents",
    "daily_product_prices",
    "daily_product_platform_prices",
    "scrape_tasks",
    "product_activity_hourly",
]

with psycopg.connect(URL) as conn:
    with conn.cursor() as cur:
        missing = []
        for name in REQUIRED:
            cur.execute("select to_regclass(%s)", (f"public.{name}",))
            if cur.fetchone()[0] is None:
                missing.append(name)
        cur.execute(
            """
            select column_name from information_schema.columns
            where table_name = 'user_wishlist'
              and column_name in ('target_price', 'notify_on_drop')
            order by 1
            """
        )
        cols = [r[0] for r in cur.fetchall()]
        cur.execute(
            """
            select table_name from information_schema.views
            where table_schema = 'public'
              and table_name ilike '%best_price%'
            order by 1
            """
        )
        views = [r[0] for r in cur.fetchall()]
        cur.execute(
            """
            select routine_name from information_schema.routines
            where routine_schema = 'public'
              and routine_name ilike '%price%'
            order by 1
            """
        )
        routines = [r[0] for r in cur.fetchall()]

print("missing_tables", missing or "none")
print("wishlist_watch_cols", cols)
print("best_price_views", views)
print("best_price_routines", routines)
if missing:
    sys.exit(1)
if "current_product_best_prices" not in views:
    print("ERROR: current_product_best_prices view missing")
    sys.exit(1)
