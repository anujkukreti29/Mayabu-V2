"""Mayabu industrial JSON catalogue and merger.

The catalogue stores three separate layers:
1. products: canonical product clusters.
2. listings: stable platform listings such as amazon:B0..., flipkart:COM..., croma:318965.
3. observations: every scrape-time price observation for a listing.

This is intentionally JSON-first so it can power an MVP without a database, while
keeping the same shape that can later move to PostgreSQL tables.
"""

from __future__ import annotations

import argparse
import difflib
from collections import defaultdict
from typing import Any, Optional

from mayabu_common import (
    canonical_platform,
    extract_specs,
    normalize_raw_listing,
    read_json,
    stable_observation_id,
    title_tokens,
    utc_now,
    write_json,
)

SCHEMA_VERSION = "mayabu.catalog.v2"
MATCH_THRESHOLD = 82.0
REVIEW_THRESHOLD = 70.0


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _round_money(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def token_jaccard(a: str, b: str) -> float:
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def seq_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _set(value: Any) -> set[str]:
    if isinstance(value, set):
        return {str(v) for v in value if v}
    if isinstance(value, list):
        return {str(v) for v in value if v}
    if value:
        return {str(value)}
    return set()


def _spec_conflicts(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    conflicts: list[str] = []
    if a.get("brand") and b.get("brand") and a["brand"] != b["brand"]:
        conflicts.append("brand")
    if a.get("category") and b.get("category") and a["category"] != b["category"]:
        conflicts.append("category")
    if a.get("family") and b.get("family") and a["family"] != b["family"]:
        conflicts.append("family")
    ma, mb = _set(a.get("model_codes")), _set(b.get("model_codes"))
    if ma and mb and not (ma & mb):
        # Model-code conflict is strong; two explicit but different model codes
        # should not live in the same product cluster.
        conflicts.append("model_code")
    ca, cb = _set(a.get("cpu_models")), _set(b.get("cpu_models"))
    if ca and cb and not (ca & cb):
        conflicts.append("cpu_model")
    if a.get("cpu_series") and b.get("cpu_series") and a["cpu_series"] != b["cpu_series"]:
        conflicts.append("cpu_series")
    if a.get("ram_gb") and b.get("ram_gb") and int(a["ram_gb"]) != int(b["ram_gb"]):
        conflicts.append("ram")
    if a.get("storage_gb") and b.get("storage_gb") and abs(int(a["storage_gb"]) - int(b["storage_gb"])) > 8:
        conflicts.append("storage")
    if a.get("screen_inch") and b.get("screen_inch") and abs(float(a["screen_inch"]) - float(b["screen_inch"])) > 0.6:
        conflicts.append("screen")
    if a.get("gpu") and b.get("gpu") and a["gpu"] != b["gpu"]:
        # integrated graphics naming is noisy, but discrete GPU mismatch matters.
        discrete = any(x in str(a.get("gpu")) + str(b.get("gpu")) for x in ["rtx", "gtx", "rx"])
        if discrete:
            conflicts.append("gpu")
    return conflicts


def score_product_match(listing: dict[str, Any], product: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    specs = listing.get("specs") or {}
    pspecs = product.get("specs") or {}
    conflicts = _spec_conflicts(specs, pspecs)
    if conflicts:
        return -100.0, {"reject": conflicts}

    title = listing.get("title_norm") or listing.get("title") or ""
    ptitle = product.get("title_norm") or product.get("canonical_title") or ""
    score = 0.0
    evidence: dict[str, Any] = {}

    if specs.get("brand") and specs.get("brand") == pspecs.get("brand"):
        score += 12
        evidence["brand"] = specs["brand"]
    if specs.get("family") and specs.get("family") == pspecs.get("family"):
        score += 32
        evidence["family"] = specs["family"]
    m_overlap = _set(specs.get("model_codes")) & _set(pspecs.get("model_codes"))
    if m_overlap:
        score += 58
        evidence["model_code"] = sorted(m_overlap)
    cpu_overlap = _set(specs.get("cpu_models")) & _set(pspecs.get("cpu_models"))
    if cpu_overlap:
        score += 32
        evidence["cpu_model"] = sorted(cpu_overlap)
    elif specs.get("cpu_series") and specs.get("cpu_series") == pspecs.get("cpu_series"):
        score += 15
        evidence["cpu_series"] = specs["cpu_series"]
    if specs.get("ram_gb") and specs.get("ram_gb") == pspecs.get("ram_gb"):
        score += 14
        evidence["ram_gb"] = specs["ram_gb"]
    if specs.get("storage_gb") and specs.get("storage_gb") == pspecs.get("storage_gb"):
        score += 12
        evidence["storage_gb"] = specs["storage_gb"]
    if specs.get("screen_inch") and pspecs.get("screen_inch") and abs(float(specs["screen_inch"]) - float(pspecs["screen_inch"])) <= 0.3:
        score += 8
        evidence["screen_inch"] = specs["screen_inch"]
    if specs.get("gpu") and specs.get("gpu") == pspecs.get("gpu"):
        score += 8
        evidence["gpu"] = specs["gpu"]

    jac = token_jaccard(title, ptitle)
    seq = seq_ratio(title, ptitle)
    score += jac * 22
    score += seq * 12
    evidence["title_jaccard"] = round(jac, 3)
    evidence["title_sequence"] = round(seq, 3)

    # Guardrail: high text similarity alone should not auto-merge electronics.
    # v4.4 capped many obvious same-product candidates below review when model
    # code was missing. v4.5 keeps trust safety but allows strong title similarity
    # + two exact signals to enter the manual-review band instead of becoming a
    # duplicate cluster by default.
    exact_signals = sum(1 for key in ["family", "model_code", "cpu_model", "ram_gb", "storage_gb", "screen_inch"] if key in evidence)
    if "model_code" not in evidence and exact_signals < 3:
        strong_text = jac >= 0.58 and seq >= 0.67
        reviewable_identity = exact_signals >= 2 and strong_text
        if reviewable_identity:
            review_score = min(max(score, REVIEW_THRESHOLD + 2), MATCH_THRESHOLD - 0.5)
            return round(review_score, 2), {**evidence, "weak_identity_review": True}
        if score < 92:
            return min(score, REVIEW_THRESHOLD - 1), {**evidence, "weak_identity": True}

    return round(score, 2), evidence


class MayabuCatalog:
    def __init__(self) -> None:
        now = utc_now()
        self.meta: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
        }
        self.products: dict[str, dict[str, Any]] = {}
        self.listings: dict[str, dict[str, Any]] = {}
        self.observations: list[dict[str, Any]] = []
        self.review_queue: list[dict[str, Any]] = []
        self.run_history: list[dict[str, Any]] = []
        self._observation_ids: set[str] = set()
        self._last_price_by_listing: dict[str, Optional[float]] = {}
        self._product_counter = 0
        self._brand_index: dict[str, set[str]] = defaultdict(set)
        self._category_index: dict[str, set[str]] = defaultdict(set)
        self._family_index: dict[tuple[str, str], set[str]] = defaultdict(set)
        self._model_index: dict[str, set[str]] = defaultdict(set)

    @classmethod
    def load(cls, path: str | None) -> "MayabuCatalog":
        cat = cls()
        if not path:
            return cat
        data = read_json(path, default=None)
        if not data:
            return cat
        if isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION:
            cat.meta = data.get("meta") or {"schema_version": SCHEMA_VERSION, "created_at": utc_now(), "updated_at": utc_now()}
            cat.products = {p["product_id"]: p for p in data.get("products", []) if isinstance(p, dict) and p.get("product_id")}
            cat.listings = {listing["listing_id"]: listing for listing in data.get("listings", []) if isinstance(listing, dict) and listing.get("listing_id")}
            cat.observations = [o for o in data.get("observations", []) if isinstance(o, dict)]
            cat.review_queue = [r for r in data.get("review_queue", []) if isinstance(r, dict)]
            cat.run_history = [r for r in data.get("run_history", []) if isinstance(r, dict)]
            cat._observation_ids = {str(o.get("observation_id")) for o in cat.observations if o.get("observation_id")}
            cat._rebuild_indexes()
            return cat
        if isinstance(data, list):
            cat._import_legacy_merged_products(data)
            return cat
        return cat

    def _rebuild_indexes(self) -> None:
        self._brand_index.clear()
        self._category_index.clear()
        self._family_index.clear()
        self._model_index.clear()
        self._last_price_by_listing.clear()
        max_id = 0
        for pid, product in self.products.items():
            try:
                max_id = max(max_id, int(pid.replace("P", "")))
            except ValueError:
                pass
            brand = (product.get("specs") or {}).get("brand") or "_unknown"
            category = product.get("category") or (product.get("specs") or {}).get("category") or "_unknown"
            self._brand_index[brand].add(pid)
            self._category_index[category].add(pid)
            family = (product.get("specs") or {}).get("family")
            if family:
                self._family_index[(brand, family)].add(pid)
            for code in _set((product.get("specs") or {}).get("model_codes")):
                self._model_index[code].add(pid)
        for obs in sorted(self.observations, key=lambda x: x.get("observed_at") or ""):
            if obs.get("listing_id") and obs.get("price") is not None:
                self._last_price_by_listing[obs["listing_id"]] = obs.get("price")
        self._product_counter = max_id

    def _import_legacy_merged_products(self, legacy: list[dict[str, Any]]) -> None:
        now = utc_now()
        for rec in legacy:
            pid = rec.get("id") or self._next_product_id()
            title = rec.get("title") or ""
            specs = extract_specs(title, "laptop")
            product = {
                "product_id": pid,
                "category": specs.get("category") or "laptop",
                "canonical_title": title,
                "title_norm": title,
                "brand": specs.get("brand"),
                "specs": specs,
                "created_at": now,
                "updated_at": now,
                "listing_ids": [],
                "source": "legacy_import",
            }
            self.products[pid] = product
            platforms = rec.get("platforms") or {}
            for platform, block in platforms.items():
                raw = {
                    "source": platform,
                    "platform": platform,
                    "title": title,
                    "price": block.get("price"),
                    "mrp": block.get("mrp"),
                    "discount_pct": block.get("discount_pct"),
                    "link": block.get("url"),
                    "image": block.get("image"),
                }
                listing = normalize_raw_listing(raw, platform_hint=platform, query=product["category"], observed_at=block.get("last_updated") or now)
                if not listing:
                    continue
                self._attach_listing_to_product(listing, pid, 999, "legacy_platform_block")
                for hist in (rec.get("price_history") or {}).get(platform, []):
                    obs_time = (hist.get("date") or block.get("last_updated") or now) + "T00:00:00+00:00"
                    self._append_observation(listing["listing_id"], hist.get("price"), block.get("mrp"), block.get("discount_pct"), obs_time)
        self._rebuild_indexes()

    def _next_product_id(self) -> str:
        self._product_counter += 1
        return f"P{self._product_counter:06d}"

    def _candidate_product_ids(self, listing: dict[str, Any]) -> list[str]:
        specs = listing.get("specs") or {}
        brand = specs.get("brand") or "_unknown"
        category = listing.get("category") or specs.get("category") or "_unknown"
        candidates: set[str] = set()

        for code in _set(specs.get("model_codes")):
            candidates |= self._model_index.get(code, set())

        family = specs.get("family")
        if family:
            candidates |= self._family_index.get((brand, family), set())

        if candidates:
            return list(candidates)

        # Broader fallback, but filtered cheaply before expensive scoring.
        pool = set(self._brand_index.get(brand, set()))
        if not pool:
            pool = set(self._category_index.get(category, set()))
        listing_title = listing.get("title_norm") or listing.get("title") or ""
        listing_tokens = title_tokens(listing_title)
        filtered: list[str] = []
        for pid in pool:
            product = self.products.get(pid, {})
            ptokens = title_tokens(product.get("title_norm") or product.get("canonical_title") or "")
            overlap = len(listing_tokens & ptokens)
            if overlap >= 2 or not listing_tokens or not ptokens:
                filtered.append(pid)
            if len(filtered) >= 120:
                break
        return filtered

    def _find_product_for_listing(self, listing: dict[str, Any]) -> tuple[Optional[str], float, str, dict[str, Any]]:
        lid = listing["listing_id"]
        if lid in self.listings:
            return self.listings[lid]["product_id"], 1000.0, "listing_id_exact", {"listing_id": lid}
        best_pid: Optional[str] = None
        best_score = -1.0
        best_evidence: dict[str, Any] = {}
        for pid in self._candidate_product_ids(listing):
            product = self.products[pid]
            score, evidence = score_product_match(listing, product)
            if score > best_score:
                best_pid, best_score, best_evidence = pid, score, evidence
        if best_pid and best_score >= MATCH_THRESHOLD:
            return best_pid, best_score, "strict_product_match", best_evidence
        if best_pid and best_score >= REVIEW_THRESHOLD:
            self.review_queue.append({
                "listing_id": listing["listing_id"],
                "candidate_product_id": best_pid,
                "score": best_score,
                "evidence": best_evidence,
                "title": listing.get("title"),
                "candidate_title": self.products[best_pid].get("canonical_title"),
                "created_at": utc_now(),
                "status": "needs_manual_review",
            })
        return None, 0.0, "new_product", {}

    def ingest_records(self, records: list[dict[str, Any]], platform_hint: str | None = None, query: str = "", observed_at: str | None = None) -> dict[str, int]:
        observed_at = observed_at or utc_now()
        stats = {"input": 0, "valid": 0, "new_products": 0, "matched_products": 0, "listings_created": 0, "listings_updated": 0, "observations_added": 0, "skipped": 0, "review_items": 0}
        before_review = len(self.review_queue)
        for raw in records:
            stats["input"] += 1
            listing = normalize_raw_listing(raw, platform_hint=platform_hint, query=query, observed_at=observed_at)
            if not listing:
                stats["skipped"] += 1
                continue
            stats["valid"] += 1
            existing_listing = listing["listing_id"] in self.listings
            pid, confidence, method, evidence = self._find_product_for_listing(listing)
            if pid is None:
                pid = self._create_product(listing)
                stats["new_products"] += 1
                method = "new_product"
            else:
                stats["matched_products"] += 1
            created = self._attach_listing_to_product(listing, pid, confidence, method, evidence)
            if created and not existing_listing:
                stats["listings_created"] += 1
            else:
                stats["listings_updated"] += 1
            if self._append_observation(listing["listing_id"], listing.get("price"), listing.get("mrp"), listing.get("discount_pct"), observed_at):
                stats["observations_added"] += 1
        stats["review_items"] = len(self.review_queue) - before_review
        self.run_history.append({"observed_at": observed_at, "platform": canonical_platform(platform_hint or "mixed"), "query": query, **stats})
        self.meta["updated_at"] = observed_at
        return stats

    def _create_product(self, listing: dict[str, Any]) -> str:
        pid = self._next_product_id()
        specs = dict(listing.get("specs") or {})
        product = {
            "product_id": pid,
            "category": listing.get("category") or specs.get("category") or "unknown",
            "canonical_title": listing.get("title") or "",
            "title_norm": listing.get("title_norm") or "",
            "brand": specs.get("brand"),
            "specs": specs,
            "created_at": listing.get("scraped_at") or utc_now(),
            "updated_at": listing.get("scraped_at") or utc_now(),
            "listing_ids": [],
            "source": "mayabu_matcher",
        }
        self.products[pid] = product
        brand_key = specs.get("brand") or "_unknown"
        self._brand_index[brand_key].add(pid)
        self._category_index[product["category"]].add(pid)
        if specs.get("family"):
            self._family_index[(brand_key, specs["family"])].add(pid)
        for code in _set(specs.get("model_codes")):
            self._model_index[code].add(pid)
        return pid

    def _merge_product_specs(self, product: dict[str, Any], listing_specs: dict[str, Any]) -> None:
        specs = product.setdefault("specs", {})
        for key, value in listing_specs.items():
            if value in (None, "", [], {}):
                continue
            if key in {"model_codes", "cpu_models"}:
                merged = sorted(_set(specs.get(key)) | _set(value))
                specs[key] = merged
            elif specs.get(key) in (None, "", [], {}):
                specs[key] = value
        product["brand"] = specs.get("brand") or product.get("brand")

    def _attach_listing_to_product(self, listing: dict[str, Any], product_id: str, confidence: float, method: str, evidence: Optional[dict[str, Any]] = None) -> bool:
        lid = listing["listing_id"]
        now = listing.get("scraped_at") or utc_now()
        created = lid not in self.listings
        product = self.products[product_id]
        if created:
            self.listings[lid] = {
                "listing_id": lid,
                "product_id": product_id,
                "platform": listing["platform"],
                "native_id": listing.get("native_id"),
                "url": listing.get("url"),
                "title": listing.get("title"),
                "title_norm": listing.get("title_norm"),
                "image": listing.get("image"),
                "category": listing.get("category"),
                "specs": listing.get("specs") or {},
                "first_seen": now,
                "last_seen": now,
                "current_price": _round_money(listing.get("price")),
                "current_mrp": _round_money(listing.get("mrp")),
                "current_discount_pct": listing.get("discount_pct"),
                "match_confidence": round(confidence, 2),
                "match_method": method,
                "match_evidence": evidence or {},
                "observation_count": 0,
            }
            product.setdefault("listing_ids", []).append(lid)
        else:
            existing = self.listings[lid]
            existing.update({
                "last_seen": now,
                "url": listing.get("url") or existing.get("url"),
                "title": listing.get("title") or existing.get("title"),
                "title_norm": listing.get("title_norm") or existing.get("title_norm"),
                "image": listing.get("image") or existing.get("image"),
                "current_price": _round_money(listing.get("price")),
                "current_mrp": _round_money(listing.get("mrp")),
                "current_discount_pct": listing.get("discount_pct"),
                "match_confidence": round(confidence, 2),
                "match_method": method,
                "match_evidence": evidence or existing.get("match_evidence") or {},
            })
            if lid not in product.setdefault("listing_ids", []):
                product["listing_ids"].append(lid)
        self._merge_product_specs(product, listing.get("specs") or {})
        # Prefer the richest title that contains a model code or more specs.
        current_title = product.get("canonical_title") or ""
        new_title = listing.get("title") or ""
        if len(new_title) > len(current_title) and not method.startswith("legacy"):
            product["canonical_title"] = new_title
            product["title_norm"] = listing.get("title_norm") or new_title
        product["updated_at"] = now
        return created

    def _append_observation(self, lid: str, price: Optional[float], mrp: Optional[float], discount_pct: Optional[float], observed_at: str) -> bool:
        if lid not in self.listings:
            return False
        obs_id = stable_observation_id(lid, observed_at, price, mrp)
        if obs_id in self._observation_ids:
            return False
        last_price = self._last_price_by_listing.get(lid)
        event_type = "initial"
        if last_price is not None and price is not None:
            if price < last_price:
                event_type = "drop"
            elif price > last_price:
                event_type = "rise"
            else:
                event_type = "unchanged"
        obs = {
            "observation_id": obs_id,
            "listing_id": lid,
            "product_id": self.listings[lid]["product_id"],
            "platform": self.listings[lid]["platform"],
            "observed_at": observed_at,
            "date": observed_at[:10],
            "price": _round_money(price),
            "mrp": _round_money(mrp),
            "discount_pct": round(float(discount_pct), 2) if discount_pct is not None else None,
            "event_type": event_type,
        }
        self.observations.append(obs)
        self._observation_ids.add(obs_id)
        self.listings[lid]["observation_count"] = int(self.listings[lid].get("observation_count") or 0) + 1
        if price is not None:
            self._last_price_by_listing[lid] = _round_money(price)
        return True

    def frontend_products(self) -> list[dict[str, Any]]:
        observations_by_listing: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for obs in self.observations:
            observations_by_listing[obs["listing_id"]].append(obs)
        output: list[dict[str, Any]] = []
        for product in self.products.values():
            platform_blocks: dict[str, dict[str, Any]] = {}
            price_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
            source_listings: list[dict[str, Any]] = []
            for lid in product.get("listing_ids", []):
                listing = self.listings.get(lid)
                if not listing:
                    continue
                platform = listing["platform"]
                hist = sorted(observations_by_listing.get(lid, []), key=lambda x: x.get("observed_at") or "")
                for obs in hist:
                    price_history[platform].append({
                        "listing_id": lid,
                        "price": obs.get("price"),
                        "mrp": obs.get("mrp"),
                        "date": obs.get("date"),
                        "observed_at": obs.get("observed_at"),
                        "type": obs.get("event_type"),
                    })
                source_listings.append({
                    "listing_id": lid,
                    "platform": platform,
                    "native_id": listing.get("native_id"),
                    "title": listing.get("title"),
                    "price": listing.get("current_price"),
                    "mrp": listing.get("current_mrp"),
                    "url": listing.get("url"),
                    "image": listing.get("image"),
                    "match_confidence": listing.get("match_confidence"),
                    "match_method": listing.get("match_method"),
                })
                current_price = listing.get("current_price")
                old = platform_blocks.get(platform)
                if current_price is not None and (old is None or old.get("price") is None or current_price < old["price"]):
                    platform_blocks[platform] = {
                        "listing_id": lid,
                        "price": current_price,
                        "mrp": listing.get("current_mrp"),
                        "discount_pct": listing.get("current_discount_pct"),
                        "url": listing.get("url"),
                        "image": listing.get("image"),
                        "last_updated": listing.get("last_seen"),
                    }
            valid_prices = [(p, data["price"]) for p, data in platform_blocks.items() if data.get("price") is not None]
            best_platform = best_price = None
            if valid_prices:
                best_platform, best_price = min(valid_prices, key=lambda x: x[1])
            all_prices = [obs.get("price") for obs in self.observations if obs.get("product_id") == product["product_id"] and obs.get("price") is not None]
            all_time_low = min(all_prices) if all_prices else None
            output.append({
                "id": product["product_id"],
                "title": product.get("canonical_title"),
                "category": product.get("category"),
                "brand": product.get("brand"),
                "specs": product.get("specs"),
                "platforms": platform_blocks,
                "price_history": dict(price_history),
                "best_price": best_price,
                "best_platform": best_platform,
                "all_time_low": all_time_low,
                "source_listings": source_listings,
            })
        output.sort(key=lambda p: (p.get("best_price") is None, p.get("best_price") or 10**12, p.get("title") or ""))
        return output

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "meta": self.meta,
            "products": sorted(self.products.values(), key=lambda x: x["product_id"]),
            "listings": sorted(self.listings.values(), key=lambda x: x["listing_id"]),
            "observations": sorted(self.observations, key=lambda x: (x.get("observed_at") or "", x.get("listing_id") or "")),
            "frontend_products": self.frontend_products(),
            "review_queue": self.review_queue,
            "run_history": self.run_history,
            "summary": self.summary(),
        }

    def summary(self) -> dict[str, Any]:
        multi = 0
        for p in self.products.values():
            platforms = {self.listings[lid]["platform"] for lid in p.get("listing_ids", []) if lid in self.listings}
            if len(platforms) > 1:
                multi += 1
        return {
            "products": len(self.products),
            "listings": len(self.listings),
            "observations": len(self.observations),
            "multi_platform_products": multi,
            "review_queue": len(self.review_queue),
        }

    def save(self, path: str) -> None:
        write_json(path, self.to_json())


def load_raw_file(path: str) -> tuple[str | None, str, list[dict[str, Any]], str | None]:
    data = read_json(path, default=[])
    if isinstance(data, dict) and data.get("records") is not None:
        return data.get("platform"), data.get("query") or "", _as_list(data.get("records")), data.get("scraped_at")
    if isinstance(data, list):
        return None, "", data, None
    return None, "", [], None


def merge_files(files: dict[str, str | None], catalog_path: str, output_path: str, query: str = "") -> MayabuCatalog:
    cat = MayabuCatalog.load(catalog_path if catalog_path else None)
    for platform, path in files.items():
        if not path:
            continue
        file_platform, file_query, records, observed_at = load_raw_file(path)
        hint = platform if platform != "auto" else file_platform
        stats = cat.ingest_records(records, platform_hint=hint, query=query or file_query, observed_at=observed_at)
        print(f"[{hint}] {path}: {stats}")
    cat.save(output_path)
    print(f"Saved catalogue -> {output_path}")
    print(cat.summary())
    return cat


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu v2 product merger/catalogue")
    parser.add_argument("--catalog", default="mayabu_catalog.json", help="Existing catalogue to update; also used if output does not exist")
    parser.add_argument("--output", default="mayabu_catalog.json")
    parser.add_argument("--query", default="")
    parser.add_argument("--amazon")
    parser.add_argument("--flipkart")
    parser.add_argument("--croma")
    parser.add_argument("--reliance")
    args = parser.parse_args()
    merge_files(
        {
            "amazon": args.amazon,
            "flipkart": args.flipkart,
            "croma": args.croma,
            "reliancedigital": args.reliance,
        },
        catalog_path=args.catalog,
        output_path=args.output,
        query=args.query,
    )


if __name__ == "__main__":
    main()
