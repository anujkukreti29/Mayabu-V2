import psycopg, os
url=os.environ.get("MAYABU_TEST_DATABASE_URL","postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_ux_harden_test")
with psycopg.connect(url) as c, c.cursor() as cur:
  cur.execute("""select column_name from information_schema.columns where table_name='product_search_documents' order by ordinal_position""")
  print([r[0] for r in cur.fetchall()])
