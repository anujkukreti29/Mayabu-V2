from mayabu_db.connection import db_connection

QUERIES = (
    "55 inch tv",
    "65 inch tv",
    "75 inch tv",
    "hisense tv",
    "led tv",
    "lg tv",
    "lg oled tv",
)
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query, status, left(coalesce(last_error,''), 80) err,
               result
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and coalesce(metadata->>'category','') = 'television'
          and platform = 'flipkart'
          and query = any(%s)
        """,
        (list(QUERIES),),
    )
    for row in cur.fetchall():
        result = row["result"]
        print("---", row["query"], row["status"], row["err"])
        if isinstance(result, dict):
            print({k: result.get(k) for k in list(result)[:12]})
        else:
            print(str(result)[:300])
