import psycopg

url = "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_ux_harden_test"
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            select table_name from information_schema.views
            where table_schema='public' and table_name ilike '%best%'
            order by 1
            """
        )
        print("views", [r[0] for r in cur.fetchall()])
        cur.execute(
            """
            select routine_name from information_schema.routines
            where routine_schema='public'
              and (routine_name ilike '%price%' or routine_name ilike '%best%')
            order by 1
            """
        )
        print("routines", [r[0] for r in cur.fetchall()])
        for name in (
            "current_product_best_prices",
            "users",
            "user_wishlist",
            "search_queries",
            "daily_product_prices",
            "daily_product_platform_prices",
            "scrape_tasks",
            "product_activity_hourly",
        ):
            cur.execute("select to_regclass(%s)", (f"public.{name}",))
            print(name, cur.fetchone()[0])
