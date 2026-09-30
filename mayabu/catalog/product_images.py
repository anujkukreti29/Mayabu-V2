"""Canonical product image gallery helpers."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from psycopg import Connection
from psycopg.errors import UndefinedTable

from mayabu.db.connection import db_connection

_BAD_URL = re.compile(
    r"(1x1|pixel|spacer|logo|banner|placeholder|tracking|sprite|badge|icon[_-]?only)",
    re.I,
)
_MAX_GALLERY = 10


def normalize_image_url(url: str | None) -> str | None:
    raw = (url or "").strip()
    if not raw or raw.startswith("data:") or "javascript:" in raw.lower():
        return None
    if raw.startswith("//"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    path = parsed.path
    query = parsed.query
    # Canonicalize common retailer CDN resize/query variants without collapsing angles.
    if "flixcart.com" in host or "flipkart" in host:
        # Keep path; drop width/quality transforms commonly used for thumbs.
        from urllib.parse import parse_qsl, urlencode

        kept = [
            (k, v)
            for k, v in parse_qsl(query, keep_blank_values=True)
            if k.lower() not in {"q", "quality", "w", "h", "width", "height", "crop"}
        ]
        query = urlencode(kept)
        path = re.sub(r"/(?:128|200|312|416|832)(?:/(?:128|200|312|416|832))?/", "/", path)
    elif "amazon" in host or "media-amazon" in host or "ssl-images-amazon" in host:
        # Strip size suffixes like ._SX300_ / ._AC_UL320_
        path = re.sub(r"\._[A-Z0-9_,]+_\.", ".", path, flags=re.I)
        query = ""
    elif "reliancedigital" in host or "jiomart" in host:
        from urllib.parse import parse_qsl, urlencode

        kept = [
            (k, v)
            for k, v in parse_qsl(query, keep_blank_values=True)
            if k.lower() not in {"w", "h", "width", "height", "auto"}
        ]
        query = urlencode(kept)
    clean = urlunparse((parsed.scheme, host, path, "", query, ""))
    if _BAD_URL.search(clean):
        return None
    return clean


def image_dedupe_key(url: str) -> str:
    """Stable key for CDN variants of the same binary asset."""
    norm = normalize_image_url(url) or (url or "").strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def url_hash(url: str) -> str:
    return image_dedupe_key(url)


def upsert_product_images(
    conn: Connection,
    *,
    product_id: str,
    urls: list[str],
    listing_id: str | None = None,
    source_platform: str | None = None,
) -> int:
    """Insert/refresh gallery URLs. First valid URL becomes primary if none set."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        norm = normalize_image_url(raw)
        if not norm:
            continue
        key = image_dedupe_key(norm)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(norm)
        if len(cleaned) >= _MAX_GALLERY:
            break
    if not cleaned:
        return 0
    inserted = 0
    with conn.cursor() as cur:
        cur.execute("savepoint product_images_upsert")
        try:
            cur.execute(
                "select 1 from product_images where product_id = %s and is_primary = true and active = true limit 1",
                (product_id,),
            )
            has_primary = cur.fetchone() is not None
            for index, url in enumerate(cleaned):
                is_primary = (not has_primary and index == 0)
                cur.execute(
                    """
                    insert into product_images(
                      product_id, listing_id, image_url, url_hash, source_platform,
                      source_position, image_role, is_primary, active, last_seen_at
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s,true,now())
                    on conflict (product_id, url_hash) do update set
                      listing_id = coalesce(excluded.listing_id, product_images.listing_id),
                      source_platform = coalesce(excluded.source_platform, product_images.source_platform),
                      source_position = least(product_images.source_position, excluded.source_position),
                      last_seen_at = now(),
                      active = true
                    """,
                    (
                        product_id,
                        listing_id,
                        url,
                        url_hash(url),
                        source_platform,
                        index,
                        "primary" if is_primary else "gallery",
                        is_primary,
                    ),
                )
                inserted += 1
                if is_primary:
                    has_primary = True
            cur.execute("release savepoint product_images_upsert")
        except UndefinedTable:
            cur.execute("rollback to savepoint product_images_upsert")
            return 0
    return inserted


def list_product_images(product_id: str, *, limit: int = _MAX_GALLERY) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("savepoint product_images_list")
            try:
                cur.execute(
                    """
                    select image_url, source_platform, source_position, image_role, is_primary
                    from product_images
                    where product_id = %s and active = true
                    order by is_primary desc, source_position asc, last_seen_at desc
                    limit %s
                    """,
                    (product_id, max(1, min(limit, _MAX_GALLERY))),
                )
                rows = [dict(r) for r in cur.fetchall()]
                cur.execute("release savepoint product_images_list")
                return rows
            except UndefinedTable:
                cur.execute("rollback to savepoint product_images_list")
                return []


__all__ = [
    "list_product_images",
    "normalize_image_url",
    "upsert_product_images",
    "url_hash",
]
