"""Admin API routes protected by X-Mayabu-Admin-Token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from mayabu.admin.audit import list_admin_actions, record_admin_action
from mayabu.core.security import ok_response, require_admin_token
from mayabu.db.connection import db_connection
from mayabu.jobs.queue import enqueue_direct_ingest, enqueue_maintenance, get_task
from mayabu.monitoring.metrics import live_verification_summary
from mayabu.monitoring.reports import list_anomalies, list_review_items, list_tasks, pause_platform, resume_platform
from mayabu.scrapers.platforms import detect_platform
from mayabu.search.index_manager import drain_dirty_search_documents, get_search_index_stats
from mayabu_db.repository import approve_review_item, find_duplicate_product_candidates, merge_products, reject_review_item

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])


class ReviewActionRequest(BaseModel):
    note: str | None = None


class MergeProductsRequest(BaseModel):
    primary_product_id: str
    duplicate_product_id: str
    note: str | None = None


class DirectIngestRequest(BaseModel):
    url: str
    platform: str | None = None
    force: bool = False


@router.get("/audit-log")
def audit_log(limit: int = Query(100, ge=1, le=1000)) -> dict:
    rows = list_admin_actions(limit=limit)
    return {"items": rows, "count": len(rows)}


@router.get("/live-verification-stats")
def live_verification_stats() -> dict:
    return live_verification_summary()


@router.get("/tasks")
def tasks(status: str | None = None, limit: int = Query(50, ge=1, le=500)) -> dict:
    rows = list_tasks(status=status, limit=limit)
    return {"tasks": rows, "count": len(rows)}


@router.get("/jobs/{task_id}")
def job(task_id: str) -> dict:
    row = get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": row}


@router.post("/jobs/direct-ingest")
def direct_ingest(body: DirectIngestRequest) -> dict:
    try:
        platform = body.platform or detect_platform(body.url)
        result = enqueue_direct_ingest(body.url, platform, force=body.force)
        task = result["task"]
        record_admin_action("direct_ingest_enqueued", target_type="scrape_task", target_id=str(task["id"]), details={"platform": platform, "force": body.force})
        return {"created": result["created"], "task_id": str(task["id"]), "status": task["status"], "platform": platform}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/anomalies")
def anomalies(status: str | None = "open", limit: int = Query(50, ge=1, le=500)) -> dict:
    rows = list_anomalies(status=status, limit=limit)
    return {"anomalies": rows, "count": len(rows)}


@router.get("/review-queue")
def review_queue(status: str | None = "needs_review", review_type: str | None = None, limit: int = Query(50, ge=1, le=500)) -> dict:
    rows = list_review_items(status=status, review_type=review_type, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.post("/review-queue/{review_id}/approve")
def approve_review(review_id: str, body: ReviewActionRequest | None = None) -> dict:
    try:
        with db_connection() as conn:
            result = approve_review_item(conn, review_id, note=(body.note if body else None))
            record_admin_action("review_approved", target_type="review_item", target_id=review_id, details={"note": body.note if body else None}, conn=conn)
            return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/review-queue/{review_id}/reject")
def reject_review(review_id: str, body: ReviewActionRequest | None = None) -> dict:
    try:
        with db_connection() as conn:
            result = reject_review_item(conn, review_id, note=(body.note if body else None))
            record_admin_action("review_rejected", target_type="review_item", target_id=review_id, details={"note": body.note if body else None}, conn=conn)
            return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/products/merge")
def merge_product_clusters(body: MergeProductsRequest) -> dict:
    try:
        with db_connection() as conn:
            result = merge_products(conn, body.primary_product_id, body.duplicate_product_id, reviewer_note=body.note, source="admin_api")
            record_admin_action("products_merged", target_type="product", target_id=body.primary_product_id, details={"duplicate_product_id": body.duplicate_product_id, "note": body.note}, conn=conn)
            return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/products/find-duplicates")
def find_duplicates(limit: int = Query(100, ge=1, le=1000), min_score: float = Query(70.0, ge=0, le=250)) -> dict:
    with db_connection() as conn:
        queued = find_duplicate_product_candidates(conn, limit=limit, min_score=min_score)
        record_admin_action("duplicate_scan_requested", target_type="review_queue", details={"queued": queued, "limit": limit, "min_score": min_score}, conn=conn)
    return {"queued": queued, "limit": limit, "min_score": min_score}


@router.post("/search-index/drain")
def drain_index(limit: int = Query(250, ge=1, le=5000)) -> dict:
    result = {**drain_dirty_search_documents(limit=limit, strict=True), "stats": get_search_index_stats()}
    record_admin_action("search_index_drained", target_type="search_index", details={"limit": limit, **{k: result.get(k) for k in ("selected", "refreshed", "failed")}})
    return result


@router.post("/maintenance/{job_name}", status_code=202)
def maintenance(job_name: str) -> dict:
    try:
        result = enqueue_maintenance(job_name, created_by="admin_api")
        task = result["task"]
        record_admin_action("maintenance_enqueued", target_type="scrape_task", target_id=str(task["id"]), details={"job": job_name})
        return {"created": result["created"], "task_id": str(task["id"]), "status": task["status"], "job": job_name}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/platform/{platform}/pause")
def pause(platform: str) -> dict:
    pause_platform(platform)
    record_admin_action("platform_paused", target_type="platform", target_id=platform)
    return ok_response(platform=platform, status="paused")


@router.post("/platform/{platform}/resume")
def resume(platform: str) -> dict:
    resume_platform(platform)
    record_admin_action("platform_resumed", target_type="platform", target_id=platform)
    return ok_response(platform=platform, status="healthy")
