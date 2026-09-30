"""FastAPI application for Mayabu v5 production architecture."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from mayabu import __version__
from mayabu.api import (
    admin_routes,
    auth_routes,
    category_routes,
    compare_routes,
    health_routes,
    homepage_routes,
    product_routes,
    search_routes,
    seo_routes,
    verification_routes,
    wishlist_routes,
)
from mayabu.api.security_headers import SecurityHeadersMiddleware
from mayabu.core.config import get_app_settings
from mayabu.core.logging import configure_logging, reset_request_id, set_request_id
from mayabu.db.connection import close_connection_pool, get_connection_pool
from mayabu.search.search_repository import search_source_status, warm_search_source

configure_logging()
logger = logging.getLogger(__name__)
settings = get_app_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_connection_pool()
    thread_limiter = to_thread.current_default_thread_limiter()
    thread_limiter.total_tokens = settings.api_threadpool_tokens
    warm_search_source()
    search = search_source_status()
    logger.info(
        "mayabu_api_started",
        extra={
            "event": "startup",
            "environment": settings.environment,
            "search_mode": search["mode"],
            "search_relation": search["relation"],
            "api_workers": settings.api_workers,
            "api_threadpool_tokens": settings.api_threadpool_tokens,
            "db_pool_max_size": settings.db_pool_max_size,
            "redis_cache_enabled": settings.enable_redis_cache,
            "redis_rate_limit_enabled": settings.enable_redis_rate_limit,
            "release_version": settings.release_version or None,
            "git_sha": (settings.git_sha[:12] if settings.git_sha else None),
        },
    )
    try:
        yield
    finally:
        close_connection_pool(timeout=2.0)
        logger.info("mayabu_api_stopped", extra={"event": "shutdown"})


app = FastAPI(
    title="Mayabu Backend API",
    version=__version__,
    description="Production-oriented modular backend for product search, matching, offers, price history, and safe scraping.",
    lifespan=lifespan,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Mayabu-Admin-Token",
        "X-Mayabu-Client-Id",
        "X-Request-ID",
        "X-CSRF-Token",
    ],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    from mayabu.monitoring import instrumentation as metrics

    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = set_request_id(request_id)
    started = time.perf_counter()
    route = metrics.route_template(request.url.path)
    method = request.method
    metrics.HTTP_IN_FLIGHT.inc()
    try:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_request_error", extra={"event": "request_error"})
            response = JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request_id})
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        status_cls = metrics.status_class(response.status_code)
        metrics.HTTP_REQUESTS.inc(route=route, method=method, status_class=status_cls)
        metrics.HTTP_LATENCY.observe(duration_ms, route=route, method=method, status_class=status_cls)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        # Avoid INFO noise for health/metrics probes.
        if route not in {"/api/live", "/api/health", "/api/ready", "/api/metrics", "/"}:
            logger.info(
                "request_completed",
                extra={
                    "event": "request",
                    "duration_ms": duration_ms,
                    "status_code": response.status_code,
                    "route": route,
                    "method": method,
                },
            )
        return response
    finally:
        metrics.HTTP_IN_FLIGHT.dec()
        reset_request_id(token)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "request_id": request.headers.get("x-request-id")})


app.include_router(health_routes.router)
app.include_router(homepage_routes.router)
app.include_router(category_routes.router)
app.include_router(seo_routes.router)
app.include_router(search_routes.router)
app.include_router(compare_routes.router)
app.include_router(product_routes.router)
app.include_router(verification_routes.router)
app.include_router(auth_routes.router)
app.include_router(wishlist_routes.router)
app.include_router(admin_routes.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "mayabu-backend", "status": "ok", "version": __version__}
