from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scrape_tasks
        set status = 'dead', last_error = 'weak_model_token', updated_at = now()
        where created_by = 'catalog_overlap' and status = 'pending' and query in ('2-WAY')
        returning query
        """
    )
    print("killed", len(cur.fetchall()))
