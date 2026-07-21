from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mayabu_common import normalize_raw_listing
from mayabu_db.quality import validate_listing
from mayabu_db.variant import build_variant_key

raw = {
    "title": "Lenovo LOQ Intel Core i5 12450HX 16GB RAM 512GB SSD RTX 3050 15.6 inch Laptop",
    "currentPrice": "₹58,990",
    "maxRetailPrice": "₹79,990",
    "link": "https://www.flipkart.com/example/p/itmabc?pid=COM123&utm_source=test",
    "image": "https://example.com/img.jpg",
}
listing = normalize_raw_listing(raw, "flipkart", "laptop")
assert listing is not None
assert listing["listing_id"] == "flipkart:COM123"
assert listing["price"] == 58990.0
assert not validate_listing(listing)
assert build_variant_key(listing["specs"], listing["title_norm"])
print("Mayabu backend smoke test passed")
