"""Bounded, lease-based Mayabu worker runtime."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
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

TaskPayload: TypeAlias = dict[str, Any]
TaskResult: TypeAlias = tuple[str, dict[str, Any]]
TaskHandler: TypeAlias = Callable[[TaskPayload, str], Awaitable[TaskResult]]


class TaskLeaseLost(RuntimeError):
    """Raised when a worker no longer owns the durable task lease."""


_STOP: asyncio.Event | None = None
_CACHE = get_cache()


def _stop_event() -> asyncio.Event:
    global _STOP
    if _STOP is None:
        _STOP = asyncio.Event()
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


def _refresh_product_state(product_id: str | None) -> None:
    if not product_id:
        return
    refresh_product_search_documents([product_id])
    _CACHE.invalidate_product(product_id)


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
    max_pages = min(int(task.get("max_pages") or 2), settings.scraper_max_pages)
    max_products = min(
        int(task.get("max_products") or 50), settings.scraper_max_products
    )
    ensure_platform_available(platform)
    async with scraper_capacity.acquire(platform):
        records = await run_discovery_scraper(
            platform,
            query,
            max_pages=max_pages,
            max_products=max_products,
            output=None,
            headless=settings.scraper_headless,
            debug=settings.scraper_debug,
        )
    with db_connection() as conn:
        if not records:
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
            conn, records, platform, query, run_id=run_id, task_id=str(task["id"])
        )
    if records and stats.valid:
        record_platform_success(platform)
        if stats.affected_product_ids:
            refresh_variant_groups(stats.affected_product_ids)
            refresh_product_search_documents(stats.affected_product_ids, strict=False)
    else:
        record_platform_failure(platform, "empty_or_invalid_discovery")
    # Search pages use a short TTL and are intentionally eventually consistent.
    # Do not wipe the entire search cache after each discovery batch.
    drain_dirty_search_documents(limit=500)
    status = "empty" if not records else ("completed" if stats.valid else "partial")
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
            str(listing["product_id"]) if listing.get("product_id") else None
        )
        return "completed", stats.as_dict()
    record_platform_failure(platform, result.page_status or "refresh_failed")
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
        else:
            error = str(result.warnings or stats.errors or result.page_status)[:500]
            mark_verification_failure(
                conn,
                listing_id,
                error=error,
                base_cooldown_seconds=settings.live_verify_failure_cooldown_seconds,
                max_cooldown_seconds=settings.live_verify_max_failure_cooldown_seconds,
            )
            record_verification_event(
                conn,
                task_id=str(task["id"]),
                product_id=product_id,
                listing_id=listing_id,
                platform=platform,
                status="blocked"
                if result.page_status in {"blocked", "captcha"}
                else "failed",
                request_count=request_count,
                source=source,
                old_price=listing.get("current_price"),
                stock_status=result.stock_status,
                duration_ms=duration_ms,
                error_code=error,
            )

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
    "refresh_listing": _execute_refresh,
    "refresh_hot_product": _execute_refresh,
    "verify_listing": _execute_verification,
    "direct_ingest": _execute_direct_ingest,
    "enrichment": _execute_direct_ingest,
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


async def run_once_async(worker_id: str) -> bool:
    settings = get_app_settings()
    with db_connection() as conn:
        requeue_stuck_tasks(conn)
        record_worker_heartbeat(conn, worker_id)
        task = claim_next_task(
            conn,
            worker_id,
            lease_minutes=settings.worker_task_lease_minutes,
        )
        if not task:
            return False
        run_id = start_run(conn, task)

    try:
        async with _maintain_task_lease(str(task["id"]), worker_id):
            status, result = await execute_task(task, run_id)
        _finalize_task(task, run_id, worker_id, status, result)
        logger.info(
            "task_execution_completed",
            extra={"task_id": str(task["id"]), "run_id": run_id, "status": status},
        )
    except PlatformCapacityError as exc:
        _defer_for_capacity(task, run_id, worker_id, exc)
    except CircuitOpenError as exc:
        _fail_for_circuit(task, run_id, worker_id, exc)
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
            extra={"task_id": str(task["id"])},
        )
    except Exception as exc:
        with suppress(Exception):
            record_platform_failure(
                task.get("platform") or "unknown", type(exc).__name__
            )
        with suppress(Exception):
            _record_verification_exception(task, exc)
        _record_unexpected_failure(task, run_id, worker_id, exc)
        logger.exception("task_execution_failed", extra={"task_id": str(task["id"])})
    finally:
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


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def stop() -> None:
        _stop_event().set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop)


async def worker_main(args: argparse.Namespace) -> None:
    global _STOP
    _STOP = asyncio.Event()
    scraper_capacity.reset()
    settings = get_app_settings()
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop)
    concurrency = (
        1
        if args.once
        else max(1, min(args.concurrency or settings.worker_concurrency, 8))
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
