from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, priority, created_by, platform, task_type, count(*)::int n
        from scrape_tasks
        where status in ('pending','running','paused')
        group by 1,2,3,4,5
        order by priority, status
        """
    )
    for row in cur.fetchall():
        print(dict(row))
