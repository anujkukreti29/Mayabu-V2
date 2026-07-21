"""Privacy-preserving client identity helpers for API throttling.

Proxy headers are ignored by default because public clients can spoof them.
Enable MAYABU_TRUST_PROXY_HEADERS only when a trusted reverse proxy strips and
replaces forwarding headers before traffic reaches the API.
"""

from __future__ import annotations

import hashlib

from fastapi import Request

from mayabu.core.config import get_app_settings


def client_identifier(request: Request) -> str:
    settings = get_app_settings()
    remote = (request.client.host if request.client else "unknown") or "unknown"
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        connecting = request.headers.get("cf-connecting-ip", "").strip()
        remote = connecting or forwarded or remote

    # A browser-generated anonymous ID improves fairness for users behind shared
    # NAT, but it is never trusted on its own and is never used for scraping.
    client_id = request.headers.get("x-mayabu-client-id", "").strip()[:128]
    raw = f"{remote}|{client_id}" if client_id else remote
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()
