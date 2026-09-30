"""Print discovery health for the overlap retailers."""
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.connection import db_connection

names = ("amazon", "vijaysales", "croma", "flipkart", "reliancedigital", "poorvika")
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select platform, status, consecutive_failures, circuit_open_until
        from platform_health
        where platform = any(%s)
        """,
        (list(names),),
    )
    rows = {row["platform"]: row for row in cur.fetchall()}
for name in names:
    row = rows.get(name) or {}
    print(
        name,
        "allows",
        platform_allows_task(name, "discovery"),
        "status",
        row.get("status"),
        "failures",
        row.get("consecutive_failures"),
        "until",
        row.get("circuit_open_until"),
    )
