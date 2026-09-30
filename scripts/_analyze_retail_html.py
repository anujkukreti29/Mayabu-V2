import json
import re
from pathlib import Path

html = Path("tmp_vs_laptop.html").read_text(encoding="utf-8", errors="ignore")
print("VS title", re.findall(r"<title>(.*?)</title>", html[:8000], re.I)[:1])
print("VS canonical", re.findall(r'rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', html, re.I)[:5])
hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
prod = [h for h in hrefs if re.search(r"/p/\d+", h)]
print("VS /p/digit unique", len(set(prod)), "samples", list(dict.fromkeys(prod))[:10])
# look for search API hints
apis = sorted(
    {
        m
        for m in re.findall(r"https?://[^\"'\\s]+", html)
        if any(t in m.lower() for t in ("search", "catalog", "product", "api", "suggest"))
    }
)
print("VS api-like", apis[:20])

htmlp = Path("tmp_pv_laptop.html").read_text(encoding="utf-8", errors="ignore")
m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', htmlp, re.I | re.S)
print("PV next_data", bool(m), "len", len(m.group(1)) if m else 0)
if m:
    data = json.loads(m.group(1))
    Path("tmp_pv_next.json").write_text(json.dumps(data)[:300000], encoding="utf-8")
    s = json.dumps(data).lower()
    print("PV top keys", list(data.keys()) if isinstance(data, dict) else type(data))
    for token in ("product", "products", "search", "hits", "items", "price", "laptop", "sku"):
        print("PV token", token, s.count(token))

htmlj = Path("tmp_jm_phone.html").read_text(encoding="utf-8", errors="ignore")
print("JM product mentions", htmlj.lower().count("product"))
print("JM selling_price", htmlj.lower().count("selling_price"), "sellingPrice", htmlj.lower().count("sellingprice"))
apisj = sorted(
    {
        m
        for m in re.findall(r"https?://[^\"'\\s<>]+", htmlj)
        if any(t in m.lower() for t in ("search", "catalog", "product", "api", "plp"))
    }
)
print("JM api-like count", len(apisj))
print("JM api samples", apisj[:25])
# Capture network-like config
for pat in (r"algolia", r"elastic", r"solr", r"__PRELOADED", r"window\.__INITIAL"):
    print("JM marker", pat, bool(re.search(pat, htmlj, re.I)))
