"""Report staging external inputs as SET/MISSING. Never prints secret values."""

from __future__ import annotations

import json
import os
import socket
import sys
from urllib.parse import urlparse

KEYS = (
    "STAGING_BASE_URL",
    "STAGING_DATABASE_URL",
    "STAGING_REDIS_URL",
    "DATABASE_URL",
    "REDIS_URL",
    "MAYABU_ALERT_WEBHOOK_URL",
    "MAYABU_AUTH_EMAIL_API_KEY",
    "MAYABU_ADMIN_TOKEN",
    "MAYABU_AUTH_PUBLIC_BASE_URL",
)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "postgres", "redis", "db", "db.internal", "redis.internal"}


def _presence(name: str) -> str:
    return "SET" if (os.getenv(name) or "").strip() else "MISSING"


def _host_class(url: str) -> dict:
    if not url.strip():
        return {"present": False}
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    local = host in _LOCAL_HOSTS or host.endswith(".local")
    query = (parsed.query or "").lower()
    if parsed.scheme in {"https", "rediss"}:
        tls = True
    elif parsed.scheme in {"postgresql", "postgres"}:
        tls = "sslmode=require" in query or "sslmode=verify-full" in query or "sslmode=verify-ca" in query
    else:
        tls = False
    return {
        "present": True,
        "scheme": parsed.scheme,
        "host_class": "local" if local else "external",
        "tls": tls,
    }


def _dns(host: str) -> dict:
    try:
        infos = socket.getaddrinfo(host, 443)
    except socket.gaierror as exc:
        return {"host": host, "resolves": False, "error": exc.strerror or "unresolved"}
    ips = sorted({item[4][0] for item in infos})
    return {"host": host, "resolves": True, "addresses": ips[:4]}


def main() -> int:
    report = {
        "secrets": {key: _presence(key) for key in KEYS},
        "database": _host_class(os.getenv("STAGING_DATABASE_URL") or os.getenv("DATABASE_URL") or ""),
        "redis": _host_class(os.getenv("STAGING_REDIS_URL") or os.getenv("REDIS_URL") or ""),
        "dns": _dns("staging.mayabu.in"),
    }
    base = (os.getenv("STAGING_BASE_URL") or "").strip()
    if base:
        host = urlparse(base).hostname or ""
        report["staging_base_dns"] = _dns(host) if host else {"resolves": False}
    blocked = (
        report["secrets"]["STAGING_BASE_URL"] == "MISSING"
        or report["database"]["host_class"] != "external"
        or report["redis"]["host_class"] != "external"
        or not report["dns"]["resolves"]
    )
    report["decision"] = "BLOCKED" if blocked else "INPUTS_PRESENT"
    json.dump(report, sys.stdout, indent=2)
    print()
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
