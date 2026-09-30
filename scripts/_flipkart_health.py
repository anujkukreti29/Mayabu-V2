from mayabu.scheduler.platform_health_policy import get_platform_status
from mayabu_db.connection import db_connection

print(get_platform_status("flipkart"))
print(get_platform_status("reliancedigital"))
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_depth' and platform = 'flipkart'
        group by 1
        """
    )
    print("tasks", [dict(r) for r in cur.fetchall()])
