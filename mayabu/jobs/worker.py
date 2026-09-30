"""Bounded, lease-based Mayabu worker runtime."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Any, TypeAlias

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection
from mayabu.jobs.maintenance import run_maintenance
from mayabu.scrapers.capacity import scraper_capacity
from mayabu.scrapers.circuit_breaker import (
    CircuitOpenError,
    ensure_platform_available,
    record_platform_failure,
    record_platform_success,
)
from mayabu.search.cache import get_cache
from mayabu.search.index_manager import (
    drain_dirty_search_documents,
    refresh_product_search_documents,
)
from mayabu.services.direct_ingestion import ingest_product_url
from mayabu.services.variant_groups import refresh_variant_groups
from mayabu.verification.verifier import verify_listing
from mayabu.verification.platform_gate import PlatformCapacityError
from mayabu.verification.repository import (
    mark_verification_failure,
    mark_verification_started,
    mark_verification_success,
    record_verification_event,
)
from mayabu_db.ingestion import ingest_records
from mayabu_db.quality import classify_empty_scrape
from mayabu_db.refresh_ingestion import apply_refresh_result, find_listing_for_refresh
from mayabu_db.repository import add_anomaly
from mayabu_db.scraper_runner import run_discovery_scraper, run_refresh_scraper
from mayabu_db.tasks import (
    claim_next_task,
    claim_task_by_id,
    complete_task,
    defer_task,
    extend_task_lease,
    fail_task,
    finish_run,
    record_worker_heartbeat,
    requeue_stuck_tasks,
    start_run,
)

logger = logging.getLogger(__name__)


class DiscoveryTimeout(TimeoutError):
    """The discovery scrape exceeded its bounded runtime."""


def discovery_task_timeout_seconds(*, max_pages: int, page_timeout_ms: int) -> float:
    """Upper bound for one discovery task, including navigation and parsing."""
    per_page = max(15.0, (page_timeout_ms / 1000) + 35.0)
    return per_page * max(1, int(max_pages)) + 15.0

TaskPayload: TypeAlias = dict[str, Any]
TaskResult: TypeAlias = tuple[str, dict[str, Any]]
TaskHandler: TypeAlias = Callable[[TaskPayload, str], Awaitable[TaskResult]]


class TaskLeaseLost(RuntimeError):
    """Raised when a worker no longer owns the durable task lease."""


_STOP: asyncio.Event | None = None
_STOP_LOOP_ID: int | None = None
_CACHE = get_cache()


def _stop_event() -> asyncio.Event:
    """Loop-local stop flag so pytest/asyncio.run() can call the worker twice."""
    global _STOP, _STOP_LOOP_ID
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if _STOP is None or _STOP_LOOP_ID != loop_id:
        _STOP = asyncio.Event()
        _STOP_LOOP_ID = loop_id
    return _STOP


async def _lease_keeper(
    task_id: str,
    worker_id: str,
    lost: asyncio.Event,
    owner: asyncio.Task[Any] | None,
) -> None:
    settings = get_app_settings()
    while not _stop_event().is_set():
        try:
            await asyncio.wait_for(
                _stop_event().wait(),
                timeout=settings.worker_lease_refresh_seconds,
            )
            return
        except asyncio.TimeoutError:
            try:
                with db_connection() as conn:
                    extended = extend_task_lease(
                        conn,
                        task_id,
                        worker_id,
                        lease_minutes=settings.worker_task_lease_minutes,
                    )
                    record_worker_heartbeat(conn, worker_id)
            except Exception:
                logger.exception(
                    "worker_lease_extension_failed",
                    extra={"task_id": task_id, "worker_id": worker_id},
                )
                continue

            if extended:
                continue
            lost.set()
            logger.error(
                "worker_task_lease_lost",
                extra={"task_id": task_id, "worker_id": worker_id},
            )
            if owner and not owner.done():
                owner.cancel()
            return


@asynccontextmanager
async def _maintain_task_lease(task_id: str, worker_id: str):
    lost = asyncio.Event()
    keeper = asyncio.create_task(
        _lease_keeper(task_id, worker_id, lost, asyncio.current_task()),
        name=f"task-lease:{task_id}",
    )
    try:
        yield
        if lost.is_set():
            raise TaskLeaseLost(f"worker lease lost for task {task_id}")
    except asyncio.CancelledError as exc:
        if lost.is_set():
            raise TaskLeaseLost(f"worker lease lost for task {task_id}") from exc
        raise
    finally:
        keeper.cancel()
        with suppress(asyncio.CancelledError):
            await keeper


def _is_verification_task(task: TaskPayload) -> bool:
    return task.get("task_type") == "verify_listing"


def _clear_verification_job_cache(task: TaskPayload) -> None:
    if _is_verification_task(task):
        _CACHE.delete(f"verification:job:{task['id']}")


def _refresh_product_state(product_id: str | None, *, material_change: bool = True) -> None:
    if not product_id:
        return
    refresh_product_search_documents([product_id])
    _CACHE.invalidate_product(product_id)
    if not material_change:
        return
    # Homepage discovery mixes freshness/best-price sections; drop the short TTL snapshot.
    try:
        from mayabu.search.homepage_discovery import HOMEPAGE_CACHE_KEY

        _CACHE.delete(HOMEPAGE_CACHE_KEY)
    except Exception:
        pass


def _resolve_listing(task: TaskPayload, task_label: str) -> dict[str, Any]:
    with db_connection() as conn:
        listing = find_listing_for_refresh(conn, task)
    if not listing:
        raise ValueError(f"{task_label} task could not resolve a platform listing")
    return listing


async def _execute_discovery(task: TaskPayload, run_id: str) -> TaskResult:
    settings = get_app_settings()
    platform = task["platform"]
    query = task.get("query") or "laptop"
    category = str((task.get("metadata") or {}).get("category") or query or "unknown")[:40]
    max_pages = min(int(task.get("max_pages") or 2), settings.scraper_max_pages)
    max_products = min(
        int(task.get("max_products") or 50), settings.scraper_max_products
    )
    metadata = task.get("metadata") or {}
    try:
        start_page = max(1, int(metadata.get("start_page") or 1))
    except (TypeError, ValueError):
        start_page = 1
    ensure_platform_available(platform)
    from mayabu.monitoring import instrumentation as metrics

    scrape_started = time.perf_counter()
    task_timeout = discovery_task_timeout_seconds(
        max_pages=max_pages,
        page_timeout_ms=settings.scraper_timeout_ms,
    )
    async with scraper_capacity.acquire(platform):
        try:
            records = await asyncio.wait_for(
                run_discovery_scraper(
                    platform,
                    query,
                    max_pages=max_pages,
                    max_products=max_products,
                    output=None,
                    headless=settings.scraper_headless,
                    debug=settings.scraper_debug,
                    start_page=start_page,
                ),
                timeout=task_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise DiscoveryTimeout(
                f"discovery exceeded {task_timeout:.0f}s"
            ) from exc
    metrics.SCRAPER_DURATION.observe(
        (time.perf_counter() - scrape_started) * 1000,
        platform=platform,
        category=category,
        scrape_type="discovery",
    )
    with db_connection() as conn:
        if not records:
            metrics.SCRAPER_EMPTY.inc(
                platform=platform, category=category, scrape_type="discovery"
            )
            anomaly = classify_empty_scrape(platform, task.get("url") or query)
            add_anomaly(
                conn,
                anomaly["severity"],
                anomaly["event_type"],
                anomaly["message"],
                platform=platform,
                run_id=run_id,
                evidence=anomaly["evidence"],
            )
        stats = ingest_records(
            conn,
            records,
            platform,
            query,
            run_id=run_id,
            task_id=str(task["id"]),
            preferred_product_id=str(metadata.get("anchor_product_id") or "") or None,
            allow_new_product=str(metadata.get("purpose") or "") != "catalog_overlap_v2",
        )
    from mayabu.scrapers.page_saturation import current_page_run, natural_stop

    page_run = current_page_run()
    natural = bool(page_run and natural_stop(page_run.stop_reason))
    # A later page with zero cards is the end of the result set, not an outage.
    overlap = str(metadata.get("purpose") or "") == "catalog_overlap_v2"
    if not records and (start_page > 1 or overlap):
        natural = True
        if page_run is not None and not page_run.stop_reason:
            page_run.stop_reason = "empty_page"
    if records and stats.valid:
        metrics.SCRAPER_RECORDS.inc(
            amount=float(getattr(stats, "valid", len(records)) or len(records)),
            platform=platform,
            category=category,
            outcome="accepted",
        )
        record_platform_success(platform)
        if stats.affected_product_ids:
            refresh_variant_groups(stats.affected_product_ids)
            refresh_product_search_documents(stats.affected_product_ids, strict=False)
    else:
        if records:
            metrics.SCRAPER_RECORDS.inc(
                amount=float(len(records)),
                platform=platform,
                category=category,
                outcome="rejected",
            )
            # Amazon weak-PLP recovery: brand-only / marketing titles yield 0 valid.
            # Enqueue bounded PDP enrichment for URL-bearing cards — never exact-match from PLP.
            if platform == "amazon" and not stats.valid:
                try:
                    from mayabu.catalog.enrichment import ENRICH_PRIORITY
                    from mayabu.catalog.title_quality import is_marketing_bullet_title
                    from mayabu_db.tasks import create_task

                    enqueued = 0
                    with db_connection() as conn:
                        for raw in records[:4]:
                            if enqueued >= 3:
                                break
                            title = str(
                                (raw or {}).get("title")
                                or (raw or {}).get("product_title")
                                or ""
                            )
                            url = str((raw or {}).get("url") or (raw or {}).get("listing_url") or "")
                            if not url or "amazon." not in url.lower():
                                continue
                            if title and not is_marketing_bullet_title(title) and len(title) >= 16:
                                continue
                            import hashlib

                            key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
                            create_task(
                                conn,
                                "amazon",
                                "enrich_listing",
                                url=url,
                                priority=ENRICH_PRIORITY,
                                metadata={
                                    "source": "amazon_weak_plp_v3",
                                    "category": category,
                                    "purpose": "pdp_identity_recovery",
                                    "weak_plp_title": title[:80],
                                },
                                idempotency_key=f"amazon_weak_plp:{key}",
                                created_by="worker",
                            )
                            enqueued += 1
                except Exception:
                    logger.exception("amazon_weak_plp_enqueue_failed")
        if not natural:
            record_platform_failure(platform, "empty_or_invalid_discovery")
    # Search pages use a short TTL and are intentionally eventually consistent.
    # Do not wipe the entire search cache after each discovery batch.
    drain_dirty_search_documents(limit=500)
    if not records and (start_page > 1 or overlap):
        # End of the result set, or an overlap search with no candidate cards.
        # Completing the task avoids retrying the same empty page.
        status = "completed"
    else:
        status = "empty" if not records else ("completed" if stats.valid else "partial")
    try:
        metrics.DISCOVERY_TOTAL.inc(platform=platform, category=category, result=status)
    except Exception:
        pass
    plan_id = str(metadata.get("scheduler_plan_id") or "")
    if plan_id:
        try:
            from mayabu.scheduler.discovery_cursor import persist_plan_cursor, supports_page_cursor

            from mayabu.scrapers.page_saturation import EMERGENCY_PAGE

            if page_run and page_run.last_page:
                last_page = page_run.last_page
                stop_reason = page_run.stop_reason
                new_ids = page_run.new_ids
                duplicate_ids = page_run.duplicate_ids
                consecutive_no_new = page_run.consecutive_no_new
            else:
                pages_fetched = max(1, max_pages)
                if not records and start_page > 1:
                    last_page = start_page
                    stop_reason = "empty_page"
                else:
                    last_page = start_page + pages_fetched - 1
                    stop_reason = ""
                new_ids = None
                duplicate_ids = None
                consecutive_no_new = None
            if int(last_page) >= EMERGENCY_PAGE and stop_reason in {"", "page_budget", "product_budget"}:
                stop_reason = "emergency_ceiling"
            persist_plan_cursor(
                plan_id,
                last_page=last_page,
                listings_found=len(records or []),
                mode="page_offset" if supports_page_cursor(platform) else "bounded_restart",
                stop_reason=stop_reason,
                new_ids=new_ids,
                duplicate_ids=duplicate_ids,
                consecutive_no_new=consecutive_no_new,
            )
        except Exception:
            logger.exception("discovery_cursor_persist_failed")
    return status, stats.as_dict()


async def _execute_refresh(task: TaskPayload, run_id: str) -> TaskResult:
    platform = task["platform"]
    ensure_platform_available(platform)
    settings = get_app_settings()
    listing = _resolve_listing(task, "refresh_listing")
    url = task.get("url") or listing.get("listing_url")
    if not url:
        raise ValueError("refresh_listing task has no URL")
    async with scraper_capacity.acquire(platform):
        result = await run_refresh_scraper(
            platform,
            url,
            headless=settings.scraper_headless,
            debug=settings.scraper_debug,
        )
    with db_connection() as conn:
        stats = apply_refresh_result(conn, listing, result, run_id=run_id)
    if stats.valid:
        record_platform_success(platform)
        _refresh_product_state(
            str(listing["product_id"]) if listing.get("product_id") else None,
            material_change=stats.last_event_type != "unchanged",
        )
        return "completed", stats.as_dict()
    from mayabu.scheduler.error_classes import classify_refresh_failure

    error_class = classify_refresh_failure(result)
    logger.info(
        "refresh_listing_failed",
        extra={
            "platform": platform,
            "task_type": "refresh_listing",
            "result": "failed",
            "error_class": error_class,
            "page_status": result.page_status,
            "task_id": str(task.get("id") or ""),
        },
    )
    record_platform_failure(platform, error_class)
    return "failed", stats.as_dict()


async def _execute_verification(task: TaskPayload, run_id: str) -> TaskResult:
    settings = get_app_settings()
    platform = task["platform"]
    ensure_platform_available(platform)
    listing = _resolve_listing(task, "verify_listing")
    url = task.get("url") or listing.get("listing_url")
    if not url:
        raise ValueError("verify_listing task has no URL")

    started = time.perf_counter()
    source = "lightweight"
    result = None
    async with scraper_capacity.acquire(platform):
        with db_connection() as conn:
            mark_verification_started(conn, str(listing["id"]))
        outcome = await verify_listing(platform, url, settings)
        result = outcome.result
        source = outcome.source

    duration_ms = int((time.perf_counter() - started) * 1000)
    listing_id = str(listing["id"])
    product_id = str(listing["product_id"]) if listing.get("product_id") else None
    request_count = int(task.get("request_count") or 1)
    with db_connection() as conn:
        stats = apply_refresh_result(
            conn, listing, result, run_id=run_id, update_stock=True
        )
        if stats.valid:
            status = (
                "out_of_stock" if result.stock_status == "out_of_stock" else "verified"
            )
            mark_verification_success(
                conn,
                listing_id,
                source=source,
                cooldown_seconds=settings.live_verify_cooldown_seconds,
                status=status,
            )
            record_verification_event(
                conn,
                task_id=str(task["id"]),
                product_id=product_id,
                listing_id=listing_id,
                platform=platform,
                status="verified",
                request_count=request_count,
                source=source,
                old_price=listing.get("current_price"),
                verified_price=result.current_price,
                stock_status=result.stock_status,
                duration_ms=duration_ms,
            )
            store_result = (
                "out_of_stock" if result.stock_status == "out_of_stock" else "success"
            )
            try:
                from mayabu.monitoring import instrumentation as metrics

                metrics.USER_PRICE_VERIFICATION_STORE.inc(
                    platform=str(platform)[:40], result=store_result
                )
            except Exception:
                pass
        else:
            error = str(result.warnings or stats.errors or result.page_status)[:500]
            mark_verification_failure(
                conn,
                listing_id,
                error=error,
                base_cooldown_seconds=settings.live_verify_failure_cooldown_seconds,
                max_cooldown_seconds=settings.live_verify_max_failure_cooldown_seconds,
            )
            fail_status = (
                "blocked"
                if result.page_status in {"blocked", "captcha"}
                else "failed"
            )
            record_verification_event(
                conn,
                task_id=str(task["id"]),
                product_id=product_id,
                listing_id=listing_id,
                platform=platform,
                status=fail_status,
                request_count=request_count,
                source=source,
                old_price=listing.get("current_price"),
                stock_status=result.stock_status,
                duration_ms=duration_ms,
                error_code=error,
            )
            try:
                from mayabu.monitoring import instrumentation as metrics

                metrics.USER_PRICE_VERIFICATION_STORE.inc(
                    platform=str(platform)[:40], result=fail_status
                )
            except Exception:
                pass

    if stats.valid:
        record_platform_success(platform)
        _refresh_product_state(product_id)
        payload = {
            "listing_id": listing_id,
            "product_id": product_id,
            "platform": platform,
            "price": result.current_price,
            "mrp": result.mrp,
            "discount_percent": result.discount_percent,
            "stock_status": result.stock_status,
            "verified_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "source": source,
            "duration_ms": duration_ms,
            "request_count": request_count,
        }
        _CACHE.set_json(
            f"verification:listing:{listing_id}",
            payload,
            settings.live_verify_cooldown_seconds,
        )
        return "completed", {**stats.as_dict(), **payload}

    record_platform_failure(platform, result.page_status or "verification_failed")
    return "failed", {
        **stats.as_dict(),
        "listing_id": listing_id,
        "platform": platform,
        "source": source,
        "duration_ms": duration_ms,
    }


async def _execute_direct_ingest(task: TaskPayload, run_id: str) -> TaskResult:
    url = task.get("url")
    if not url:
        raise ValueError("direct_ingest task requires url")
    settings = get_app_settings()
    platform = task["platform"]
    async with scraper_capacity.acquire(platform):
        result = await ingest_product_url(
            url,
            platform=platform,
            headless=settings.scraper_headless,
            debug=settings.scraper_debug,
            run_id=run_id,
            task_id=str(task["id"]),
        )
    return ("completed" if result.get("ok") else "failed"), result


async def _execute_enrich_listing(task: TaskPayload, run_id: str) -> TaskResult:
    from mayabu.catalog.enrichment import enrich_listing

    listing = _resolve_listing(task, "enrich_listing")
    settings = get_app_settings()
    result = await enrich_listing(
        listing,
        headless=settings.scraper_headless,
        debug=False,
        run_id=run_id,
    )
    return ("completed" if result.get("ok") else "failed"), result


async def _execute_targeted_discovery(task: TaskPayload, run_id: str) -> TaskResult:
    """Reuse discovery scrape path; record overlap attempt outcomes."""
    from mayabu.catalog.overlap import record_overlap_attempt_result
    from mayabu.monitoring import instrumentation as metrics

    status, payload = await _execute_discovery(task, run_id)
    metadata = task.get("metadata") or {}
    product_id = str(metadata.get("anchor_product_id") or "")
    fp = str(metadata.get("query_fingerprint") or "")
    platform = str(task.get("platform") or "")
    candidates = int((payload or {}).get("valid") or (payload or {}).get("accepted") or 0)
    if not candidates and isinstance(payload, dict):
        candidates = int(payload.get("listings_found") or payload.get("count") or 0)
    # Exact matches inferred from affected products when present
    exact = 0
    if isinstance(payload, dict):
        affected = payload.get("affected_product_ids") or []
        if product_id and product_id in {str(x) for x in affected}:
            exact = 1
    if product_id and fp:
        try:
            record_overlap_attempt_result(
                product_id=product_id,
                target_platform=platform,
                query_fingerprint=fp,
                result=status,
                candidates_found=candidates,
                exact_matches=exact,
            )
        except Exception:
            logger.exception("overlap_attempt_record_failed")
    try:
        metrics.OVERLAP_DISCOVERY.inc(platform=platform, result=status)
    except Exception:
        pass
    return status, payload


async def _execute_index_product(task: TaskPayload, run_id: str) -> TaskResult:
    del run_id
    product_id = (task.get("metadata") or {}).get("product_id")
    if not product_id:
        raise ValueError("index_product task requires metadata.product_id")
    return "completed", refresh_product_search_documents([str(product_id)], strict=True)


async def _execute_maintenance(task: TaskPayload, run_id: str) -> TaskResult:
    del run_id
    job = (task.get("metadata") or {}).get("job", "all")
    return "completed", run_maintenance(job)


_TASK_HANDLERS: dict[str, TaskHandler] = {
    "discovery": _execute_discovery,
    "discovery_search": _execute_discovery,
    "targeted_discovery": _execute_targeted_discovery,
    "refresh_listing": _execute_refresh,
    "refresh_hot_product": _execute_refresh,
    "verify_listing": _execute_verification,
    "direct_ingest": _execute_direct_ingest,
    "enrichment": _execute_direct_ingest,
    "enrich_listing": _execute_enrich_listing,
    "index_product": _execute_index_product,
    "maintenance": _execute_maintenance,
}


async def execute_task(task: TaskPayload, run_id: str) -> TaskResult:
    handler = _TASK_HANDLERS.get(str(task.get("task_type")))
    if handler is None:
        raise NotImplementedError(f"Unsupported task_type: {task.get('task_type')}")
    return await handler(task, run_id)


def _result_error(status: str, result: dict[str, Any]) -> str:
    error = result.get("error") or result.get("errors") or status
    if isinstance(error, list):
        return "; ".join(str(item) for item in error[:5])
    return str(error)


def _finalize_task(
    task: TaskPayload,
    run_id: str,
    worker_id: str,
    status: str,
    result: dict[str, Any],
) -> None:
    successful = status in {"completed", "partial"}
    error = None if successful else _result_error(status, result)
    with db_connection() as conn:
        finish_run(conn, run_id, status, result, error=error)
        if successful:
            complete_task(conn, str(task["id"]), result={"status": status, **result})
        else:
            fail_task(conn, task, error or status, result=result)
        record_worker_heartbeat(conn, worker_id, tasks_processed_delta=1)


def _defer_for_capacity(
    task: TaskPayload, run_id: str, worker_id: str, error: Exception
) -> None:
    with db_connection() as conn:
        finish_run(conn, run_id, "partial", {"deferred": True}, error=str(error))
        defer_task(conn, str(task["id"]), str(error), delay_seconds=15)
        record_worker_heartbeat(conn, worker_id, tasks_processed_delta=1)


def _fail_for_circuit(
    task: TaskPayload, run_id: str, worker_id: str, error: Exception
) -> None:
    with db_connection() as conn:
        finish_run(conn, run_id, "failed", {}, error=str(error))
        fail_task(conn, task, str(error))
        record_worker_heartbeat(conn, worker_id, tasks_processed_delta=1)


def _record_verification_exception(task: TaskPayload, error: Exception) -> None:
    if not _is_verification_task(task):
        return
    settings = get_app_settings()
    with db_connection() as conn:
        listing = find_listing_for_refresh(conn, task)
        if not listing:
            return
        error_text = f"{type(error).__name__}:{error}"[:500]
        listing_id = str(listing["id"])
        mark_verification_failure(
            conn,
            listing_id,
            error=error_text,
            base_cooldown_seconds=settings.live_verify_failure_cooldown_seconds,
            max_cooldown_seconds=settings.live_verify_max_failure_cooldown_seconds,
        )
        record_verification_event(
            conn,
            task_id=str(task["id"]),
            product_id=str(listing["product_id"])
            if listing.get("product_id")
            else None,
            listing_id=listing_id,
            platform=task.get("platform") or "unknown",
            status="failed",
            request_count=int(task.get("request_count") or 1),
            old_price=listing.get("current_price"),
            error_code=error_text,
        )


def _record_unexpected_failure(
    task: TaskPayload,
    run_id: str,
    worker_id: str,
    error: Exception,
) -> None:
    error_text = str(error)
    with db_connection() as conn:
        finish_run(conn, run_id, "failed", {"errors": [error_text]}, error=error_text)
        fail_task(conn, task, error_text)
        add_anomaly(
            conn,
            "high",
            "task_execution_failed",
            "Background task failed",
            platform=task.get("platform"),
            run_id=run_id,
            evidence={
                "error": error_text,
                "task_id": str(task["id"]),
                "task_type": task.get("task_type"),
            },
        )
        record_worker_heartbeat(conn, worker_id, tasks_processed_delta=1)


async def run_once_async(
    worker_id: str,
    *,
    task_id: str | None = None,
    created_by: str | None = None,
) -> bool:
    settings = get_app_settings()
    from mayabu.monitoring import instrumentation as metrics

    claim_started = time.perf_counter()
    with db_connection() as conn:
        requeue_stuck_tasks(conn)
        record_worker_heartbeat(conn, worker_id)
        if task_id:
            task = claim_task_by_id(
                conn,
                task_id,
                worker_id,
                lease_minutes=settings.worker_task_lease_minutes,
            )
        else:
            task = claim_next_task(
                conn,
                worker_id,
                lease_minutes=settings.worker_task_lease_minutes,
                created_by=created_by,
            )
        if not task:
            metrics.QUEUE_CLAIM.observe(
                (time.perf_counter() - claim_started) * 1000, result="empty"
            )
            return False
        run_id = start_run(conn, task)
    metrics.QUEUE_CLAIM.observe(
        (time.perf_counter() - claim_started) * 1000, result="claimed"
    )

    task_type = str(task.get("task_type") or "unknown")[:40]
    platform = str(task.get("platform") or "unknown")[:40]
    category = str((task.get("metadata") or {}).get("category") or task.get("query") or "unknown")[:40]
    exec_started = time.perf_counter()
    result_status = "failed"

    try:
        async with _maintain_task_lease(str(task["id"]), worker_id):
            status, result = await execute_task(task, run_id)
        _finalize_task(task, run_id, worker_id, status, result)
        result_status = status
        logger.info(
            "task_execution_completed",
            extra={
                "task_id": str(task["id"]),
                "run_id": run_id,
                "status": status,
                "platform": platform,
                "task_type": task_type,
                "category": category,
                "duration_ms": round((time.perf_counter() - exec_started) * 1000, 1),
            },
        )
    except PlatformCapacityError as exc:
        _defer_for_capacity(task, run_id, worker_id, exc)
        result_status = "deferred"
    except CircuitOpenError as exc:
        _fail_for_circuit(task, run_id, worker_id, exc)
        result_status = "circuit_open"
    except DiscoveryTimeout as exc:
        record_platform_failure(platform, "discovery_timeout")
        with db_connection() as conn:
            finish_run(conn, run_id, "failed", {}, error=str(exc))
            # Retry until the task budget is spent. The plan cursor is left
            # unchanged because the scrape did not finish.
            fail_task(conn, task, f"discovery_timeout: {exc}", terminal=False)
            record_worker_heartbeat(conn, worker_id, tasks_processed_delta=1)
        logger.error(
            "discovery_task_timed_out",
            extra={"task_id": str(task["id"]), "platform": platform, "task_type": task_type},
        )
        result_status = "timeout"
    except TaskLeaseLost as exc:
        # Do not mutate the task row after ownership is lost; another worker may
        # already have reclaimed it. The run record remains useful for audit.
        with suppress(Exception):
            with db_connection() as conn:
                finish_run(conn, run_id, "failed", {"lease_lost": True}, error=str(exc))
                add_anomaly(
                    conn,
                    "high",
                    "worker_task_lease_lost",
                    "Worker stopped after losing task ownership",
                    platform=task.get("platform"),
                    run_id=run_id,
                    evidence={"task_id": str(task["id"]), "worker_id": worker_id},
                )
        logger.error(
            "task_execution_stopped_after_lease_loss",
            extra={"task_id": str(task["id"]), "platform": platform, "task_type": task_type},
        )
        result_status = "lease_lost"
    except Exception as exc:
        with suppress(Exception):
            record_platform_failure(
                task.get("platform") or "unknown", type(exc).__name__
            )
        with suppress(Exception):
            _record_verification_exception(task, exc)
        _record_unexpected_failure(task, run_id, worker_id, exc)
        logger.exception(
            "task_execution_failed",
            extra={"task_id": str(task["id"]), "platform": platform, "task_type": task_type},
        )
        result_status = "failed"
    finally:
        elapsed_ms = (time.perf_counter() - exec_started) * 1000
        metrics.WORKER_TASKS.inc(task_type=task_type, platform=platform, result=result_status)
        metrics.WORKER_DURATION.observe(
            elapsed_ms, task_type=task_type, platform=platform, result=result_status
        )
        if result_status in {"empty", "completed", "partial"} and task_type in {
            "discovery",
            "discovery_search",
        }:
            # Empty discovery is an operational signal even without exception.
            pass
        _clear_verification_job_cache(task)
    return True


async def _worker_slot(worker_id: str, once: bool = False) -> None:
    settings = get_app_settings()
    while not _stop_event().is_set():
        found = await run_once_async(worker_id)
        if once:
            return
        if not found:
            try:
                await asyncio.wait_for(
                    _stop_event().wait(), timeout=settings.worker_poll_seconds
                )
            except asyncio.TimeoutError:
                pass


def _start_parent_watch(loop: asyncio.AbstractEventLoop, grace_seconds: int) -> None:
    """Shut down when the launching shell has already exited."""
    from mayabu.jobs.process_tree import console_ancestor_pid, process_alive, terminate_children

    ancestor = console_ancestor_pid()
    if not ancestor:
        return

    def watch() -> None:
        while process_alive(ancestor):
            if _STOP is not None and _STOP.is_set():
                return
            time.sleep(2)
        if _STOP is not None and _STOP.is_set():
            return
        if not loop.is_closed():
            loop.call_soon_threadsafe(_STOP.set)
        time.sleep(max(1, grace_seconds))
        terminate_children()
        os._exit(0)

    threading.Thread(target=watch, name="mayabu-parent-watch", daemon=True).start()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def stop(*_args: object) -> None:
        if loop.is_closed():
            return
        loop.call_soon_threadsafe(_stop_event().set)

    from mayabu.jobs.process_tree import install_shutdown_signals

    install_shutdown_signals(stop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, stop)


async def worker_main(args: argparse.Namespace) -> None:
    global _STOP, _STOP_LOOP_ID
    loop = asyncio.get_running_loop()
    _STOP = asyncio.Event()
    _STOP_LOOP_ID = id(loop)
    scraper_capacity.reset()
    settings = get_app_settings()
    _install_signal_handlers(loop)
    _start_parent_watch(loop, settings.worker_shutdown_grace_seconds)
    concurrency = (
        1
        if args.once
        else max(1, min(args.concurrency or settings.worker_concurrency, 8))
    )
    logger.info(
        "mayabu_worker_started",
        extra={
            "event": "startup",
            "worker_id": settings.worker_id,
            "concurrency": concurrency,
            "db_pool_max_size": settings.db_pool_max_size,
        },
    )
    tasks = [
        asyncio.create_task(
            _worker_slot(f"{settings.worker_id}-{index + 1}", once=args.once)
        )
        for index in range(concurrency)
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        _stop_event().set()
        for task in tasks:
            task.cancel()
        with suppress(Exception):
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=settings.worker_shutdown_grace_seconds,
            )
        with suppress(Exception):
            from mayabu.db.connection import close_connection_pool

            close_connection_pool(timeout=2.0)
        with suppress(Exception):
            from mayabu_refresh.browser_pool import close_refresh_browser_pool

            await close_refresh_browser_pool()
        with suppress(Exception):
            from mayabu.jobs.process_tree import terminate_children

            terminate_children()
        logger.info("mayabu_worker_stopped", extra={"event": "shutdown"})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Mayabu v5 durable background worker"
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--concurrency", type=int)
    args = parser.parse_args()
    if not args.once and not args.loop:
        args.once = True
    try:
        asyncio.run(worker_main(args))
    except KeyboardInterrupt:
        print("Worker stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
