from mayabu.search.query_parser import parse_query
from mayabu.search.search_repository import search_products

QUERIES = [
    "laptop", "MacBook", "gaming laptop", "iPhone", "Galaxy",
    "Samsung TV", "Sony TV", "refrigerator", "washing machine",
    "TWS", "Sony headphones", "camera", "Canon", "Nikon",
]
for query in QUERIES:
    rows = search_products(parse_query(query), limit=5)
    titles = [f"{(r.get('category') or '')}:{(r.get('canonical_title') or '')[:60]}" for r in rows]
    print(query, len(rows), " | ".join(titles))
