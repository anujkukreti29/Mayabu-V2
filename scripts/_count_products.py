import psycopg
c = psycopg.connect("postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu")
cur = c.cursor()
cur.execute("select count(*) from product_clusters where status = %s", ("active",))
print("active_products", cur.fetchone()[0])
cur.execute("select count(*) from product_search_documents")
print("search_docs", cur.fetchone()[0])
