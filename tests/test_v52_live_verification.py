from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from mayabu.verification import lightweight, service
from mayabu_db.refresh_ingestion import validate_refresh_result
from mayabu_refresh.models import RefreshResult


class DummyCache:
    client = None

    def __init__(self, value=None):
        self.value = value
        self.saved = {}

    def get_json(self, key):
        return self.saved.get(key, self.value)

    def set_json(self, key, value, ttl_seconds):
        self.saved[key] = value

    def set_if_absent(self, key, value, ttl_seconds):
        # Simulate Redis being unavailable so service-level DB idempotency remains the fallback.
        return None

    def delete(self, key):
        self.saved.pop(key, None)


def _settings(**overrides):
    values = {
        "live_verify_max_offers_per_request": 4,
        "live_verify_fresh_seconds": 180,
        "live_verify_queue_max_active": 2000,
        "live_verify_priority": 5,
        "live_verify_max_attempts": 2,
        "live_verify_estimated_seconds": 15,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _offer(listing_id="listing-1", price=70000, verified_at=None):
    return {
        "id": listing_id,
        "platform": "flipkart",
        "listing_url": "https://www.flipkart.com/example/p/itm1?pid=COM1",
        "current_price": price,
        "stock_status": "in_stock",
        "last_verified_at": verified_at,
        "last_successful_refresh_at": None,
        "next_allowed_verification_at": None,
    }


def test_same_listing_requests_join_one_durable_task(monkeypatch):
    monkeypatch.setattr(service, "get_app_settings", lambda: _settings())
    monkeypatch.setattr(service, "product_exists", lambda product_id: True)
    monkeypatch.setattr(service, "get_product_offers", lambda product_id: [_offer()])
    monkeypatch.setattr(service, "_CACHE", DummyCache())
    monkeypatch.setattr(
        service,
        "enqueue_verification",
        lambda **kwargs: {"created": False, "task": {"id": "task-1"}, "rejected": None},
    )
    result = service.request_price_verification("product-1", "best_offer")
    assert result["status"] == "joined"
    assert result["task_ids"] == ["task-1"]
    assert result["tasks"][0]["created"] is False


def test_recent_verification_does_not_enqueue(monkeypatch):
    monkeypatch.setattr(service, "get_app_settings", lambda: _settings())
    monkeypatch.setattr(service, "product_exists", lambda product_id: True)
    monkeypatch.setattr(service, "get_product_offers", lambda product_id: [_offer(verified_at=datetime.now(timezone.utc))])
    monkeypatch.setattr(service, "_CACHE", DummyCache())
    monkeypatch.setattr(service, "enqueue_verification", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not enqueue")))
    result = service.request_price_verification("product-1", "best_offer")
    assert result["status"] == "fresh"
    assert result["task_ids"] == []


def test_queue_capacity_returns_cached_busy_state(monkeypatch):
    monkeypatch.setattr(service, "get_app_settings", lambda: _settings(live_verify_queue_max_active=2))
    monkeypatch.setattr(service, "product_exists", lambda product_id: True)
    monkeypatch.setattr(service, "get_product_offers", lambda product_id: [_offer()])
    monkeypatch.setattr(service, "_CACHE", DummyCache())
    monkeypatch.setattr(
        service,
        "enqueue_verification",
        lambda **kwargs: {"created": False, "task": None, "rejected": "queue_busy"},
    )
    result = service.request_price_verification("product-1", "best_offer")
    assert result["status"] == "busy"
    assert result["skipped"][0]["reason"] == "queue_busy"


def test_lightweight_json_ld_extracts_price_and_stock():
    html = '''
    <script type="application/ld+json">
      {"@type":"Product","offers":{"price":"69999","availability":"https://schema.org/InStock"}}
    </script>
    '''
    price, mrp, stock = lightweight._extract_from_json_ld(html)
    assert price == 69999
    assert mrp is None
    assert stock == "in_stock"


def test_v52_schema_and_public_routes_are_present():
    root = Path(__file__).resolve().parents[1]
    schema = (root / "mayabu_db" / "schema.sql").read_text(encoding="utf-8")
    assert "task_type = 'verify_listing'" in schema
    assert "create table if not exists live_verification_events" in schema
    assert "last_verified_at" in schema
    routes = (root / "mayabu" / "api" / "verification_routes.py").read_text(encoding="utf-8")
    assert '/products/{product_id}/verify-price' in routes
    assert '/verification-jobs/{task_id}' in routes


def test_public_verification_openapi_contract_is_exposed():
    from mayabu.api.main import app

    paths = app.openapi()["paths"]
    verify = paths["/api/products/{product_id}/verify-price"]["post"]
    job = paths["/api/verification-jobs/{task_id}"]["get"]
    status = paths["/api/products/{product_id}/verification-status"]["get"]
    assert verify["requestBody"]["required"] is True
    assert "202" in verify["responses"]
    assert "200" in job["responses"]
    assert "200" in status["responses"]


def test_live_verification_accepts_out_of_stock_without_erasing_last_price():
    listing = {
        "platform": "amazon",
        "listing_url": "https://www.amazon.in/dp/B0ABCDEFGHI",
        "category": "laptop",
        "current_price": 70000,
    }
    result = RefreshResult(current_price=None, stock_status="out_of_stock", page_status="success")
    ok, flags = validate_refresh_result(listing, result, allow_out_of_stock_without_price=True)
    assert ok is True
    assert not any(flag["code"] == "missing_price" for flag in flags)


def test_live_verification_does_not_use_user_network_as_proxy():
    root = Path(__file__).resolve().parents[1]
    verification_files = list((root / "mayabu" / "verification").glob("*.py"))
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in verification_files)
    assert "x-forwarded-for" not in text
    assert "user proxy" not in text
    assert "user ip" not in text


def test_live_queue_cap_is_atomic_not_a_soft_python_check():
    root = Path(__file__).resolve().parents[1]
    queue_source = (root / "mayabu" / "jobs" / "queue.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in queue_source
    assert "task_type = 'verify_listing'" in queue_source
    assert "request_count = request_count + 1" in queue_source


def test_request_burst_reuses_short_redis_response(monkeypatch):
    class CoalescingCache(DummyCache):
        def set_if_absent(self, key, value, ttl_seconds):
            if key in self.saved:
                return False
            self.saved[key] = value
            return True

    cache = CoalescingCache()
    calls = {"count": 0}

    def enqueue(**kwargs):
        calls["count"] += 1
        return {"created": True, "task": {"id": "task-1"}, "rejected": None}

    monkeypatch.setattr(service, "get_app_settings", lambda: _settings())
    monkeypatch.setattr(service, "product_exists", lambda product_id: True)
    monkeypatch.setattr(service, "get_product_offers", lambda product_id: [_offer()])
    monkeypatch.setattr(service, "_CACHE", cache)
    monkeypatch.setattr(service, "enqueue_verification", enqueue)

    first = service.request_price_verification("product-1", "best_offer")
    second = service.request_price_verification("product-1", "best_offer")

    assert first["status"] == "queued"
    assert second["status"] == "joined"
    assert second["coalesced"] is True
    assert calls["count"] == 1


def test_global_memory_rate_limit_smooths_different_product_bursts():
    from mayabu.api.rate_limit import SlidingWindowLimiter

    class NoRedis:
        client = None

        def _available(self):
            return False

    limiter = SlidingWindowLimiter("test-global", window_seconds=60)
    limiter._cache = NoRedis()
    assert limiter.allow("client-a", per_key_limit=10, global_limit=2) == "allowed"
    assert limiter.allow("client-b", per_key_limit=10, global_limit=2) == "allowed"
    assert limiter.allow("client-c", per_key_limit=10, global_limit=2) == "global_limited"


def test_proxy_header_is_ignored_unless_explicitly_trusted(monkeypatch):
    from starlette.requests import Request

    from mayabu.api import client_identity

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"203.0.113.9")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
    }
    request = Request(scope)
    monkeypatch.setattr(client_identity, "get_app_settings", lambda: SimpleNamespace(trust_proxy_headers=False))
    untrusted = client_identity.client_identifier(request)
    monkeypatch.setattr(client_identity, "get_app_settings", lambda: SimpleNamespace(trust_proxy_headers=True))
    trusted = client_identity.client_identifier(request)
    assert untrusted != trusted


def test_verification_storage_has_bounded_retention():
    root = Path(__file__).resolve().parents[1]
    schema = (root / "mayabu_db" / "schema.sql").read_text(encoding="utf-8")
    maintenance = (root / "mayabu" / "jobs" / "maintenance.py").read_text(encoding="utf-8")
    assert "idx_live_verification_events_created_at" in schema
    assert "cleanup_live_verification_events" in maintenance


def test_production_global_limiter_fails_closed_when_redis_is_unavailable():
    from mayabu.api.rate_limit import SlidingWindowLimiter

    class ConfiguredButUnavailableRedis:
        client = None
        enabled = True

        def _available(self):
            return False

    limiter = SlidingWindowLimiter("test-fail-closed", window_seconds=60)
    limiter._cache = ConfiguredButUnavailableRedis()
    assert (
        limiter.allow(
            "client-a",
            per_key_limit=10,
            global_limit=100,
            fail_closed_global=True,
        )
        == "global_limited"
    )


def test_user_price_verification_metrics_use_inc_kwargs():
    """Regression: custom metrics registry has no .labels() — wrong API caused HTTP 500."""
    from pathlib import Path

    routes = (
        Path(__file__).resolve().parents[1] / "mayabu" / "api" / "verification_routes.py"
    ).read_text(encoding="utf-8")
    assert "USER_PRICE_VERIFICATION.inc(" in routes
    assert ".labels(" not in routes


def test_refresh_update_casts_nullable_price_comparisons():
    """Regression: NULL current_price in CASE %s IS NOT NULL caused IndeterminateDatatype ($11)."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "mayabu_db" / "refresh_ingestion.py").read_text(encoding="utf-8")
    assert "%s::numeric is not null" in source
    assert "current_price is distinct from %s::numeric" in source
