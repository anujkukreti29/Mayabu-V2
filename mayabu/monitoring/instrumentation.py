"""Named Mayabu operational metrics (bounded labels only)."""

from __future__ import annotations

from mayabu.monitoring.registry import Timer, get_registry

_REG = get_registry()

# --- API ---
HTTP_REQUESTS = _REG.counter(
    "mayabu_http_requests_total",
    "HTTP requests by route template, method, and status class",
    ("route", "method", "status_class"),
)
HTTP_IN_FLIGHT = _REG.gauge(
    "mayabu_http_in_flight",
    "In-flight HTTP requests",
    (),
)
HTTP_LATENCY = _REG.histogram(
    "mayabu_http_request_duration_ms",
    "HTTP request latency in milliseconds",
    ("route", "method", "status_class"),
)

# --- Search ---
SEARCH_TOTAL = _REG.histogram(
    "mayabu_search_duration_ms",
    "End-to-end search latency in milliseconds",
    ("category", "search_mode", "cache"),
)
SEARCH_PARSE = _REG.histogram(
    "mayabu_search_parse_duration_ms",
    "Search query parse/classify latency",
    ("category", "search_mode"),
)
SEARCH_CANDIDATES = _REG.histogram(
    "mayabu_search_candidate_duration_ms",
    "Search candidate retrieval latency",
    ("category", "search_mode"),
)
SEARCH_FACETS = _REG.histogram(
    "mayabu_search_facet_duration_ms",
    "Search facet aggregation latency",
    ("category", "search_mode"),
)
SEARCH_RANK = _REG.histogram(
    "mayabu_search_rank_duration_ms",
    "Search ranking latency",
    ("category", "search_mode"),
)
SEARCH_SERIALIZE = _REG.histogram(
    "mayabu_search_serialize_duration_ms",
    "Search response serialization latency",
    ("category", "search_mode"),
)
SEARCH_CACHE = _REG.counter(
    "mayabu_search_cache_events_total",
    "Search cache hit/miss/error events",
    ("event",),
)
SEARCH_CANDIDATE_COUNT = _REG.histogram(
    "mayabu_search_candidate_count",
    "Candidates considered for a search page",
    ("category", "search_mode"),
)
SEARCH_RESULT_COUNT = _REG.histogram(
    "mayabu_search_result_count",
    "Results returned on a search page",
    ("category", "search_mode"),
)

# --- Matching ---
MATCH_DURATION = _REG.histogram(
    "mayabu_matching_duration_ms",
    "Matching assessment latency",
    ("category", "relation"),
)
MATCH_RESULTS = _REG.counter(
    "mayabu_matching_results_total",
    "Matching classification counts",
    ("category", "relation"),
)

# --- Auth / wishlist ---
AUTH_LOGIN = _REG.counter(
    "mayabu_auth_login_total",
    "Auth login/logout outcomes",
    ("result",),
)
AUTH_REGISTER = _REG.counter(
    "mayabu_auth_register_total",
    "Auth registration/verification outcomes",
    ("result",),
)
AUTH_SESSION = _REG.counter(
    "mayabu_auth_session_validation_total",
    "Session validation outcomes",
    ("result",),
)
AUTH_SESSION_EVENT = _REG.counter(
    "mayabu_auth_session_events_total",
    "Session lifecycle events",
    ("event",),
)
EMAIL_SEND = _REG.counter(
    "mayabu_email_send_total",
    "Outbound auth email attempts",
    ("type", "result"),
)
WISHLIST_ACTION = _REG.counter(
    "mayabu_wishlist_action_total",
    "Wishlist mutations",
    ("action", "result"),
)

# --- DB ---
DB_POOL_IN_USE = _REG.gauge("mayabu_db_pool_in_use", "Approximate DB pool connections in use", ())
DB_POOL_SIZE = _REG.gauge("mayabu_db_pool_size", "Configured/current DB pool size", ())
DB_POOL_WAITING = _REG.gauge("mayabu_db_pool_waiting", "Clients waiting for a DB connection", ())
DB_ACQUIRE = _REG.histogram(
    "mayabu_db_acquire_duration_ms",
    "DB pool acquire latency",
    (),
)
DB_ACQUIRE_ERRORS = _REG.counter(
    "mayabu_db_acquire_errors_total",
    "DB pool acquire timeouts/errors",
    ("error",),
)
DB_OP = _REG.histogram(
    "mayabu_db_operation_duration_ms",
    "Logical DB operation latency",
    ("operation",),
)

# --- Queue / worker ---
QUEUE_PENDING = _REG.gauge("mayabu_queue_pending", "Pending scrape tasks", ())
QUEUE_RUNNING = _REG.gauge("mayabu_queue_running", "Running scrape tasks", ())
QUEUE_OLDEST_AGE = _REG.gauge(
    "mayabu_queue_oldest_pending_age_seconds",
    "Age of oldest pending runnable task in seconds",
    (),
)
QUEUE_CLAIM = _REG.histogram(
    "mayabu_queue_claim_duration_ms",
    "Task claim latency",
    ("result",),
)
WORKER_TASKS = _REG.counter(
    "mayabu_worker_tasks_total",
    "Worker task outcomes",
    ("task_type", "platform", "result"),
)
WORKER_DURATION = _REG.histogram(
    "mayabu_worker_task_duration_ms",
    "Worker task execution duration",
    ("task_type", "platform", "result"),
)

# --- Scraper ---
SCRAPER_DURATION = _REG.histogram(
    "mayabu_scraper_duration_ms",
    "Scraper discovery/refresh duration",
    ("platform", "category", "scrape_type"),
)
SCRAPER_RECORDS = _REG.counter(
    "mayabu_scraper_records_total",
    "Scraper record outcomes",
    ("platform", "category", "outcome"),
)
SCRAPER_EMPTY = _REG.counter(
    "mayabu_scraper_empty_total",
    "Empty scrape outcomes",
    ("platform", "category", "scrape_type"),
)
DISCOVERY_TOTAL = _REG.counter(
    "mayabu_discovery_total",
    "Scheduled discovery task outcomes",
    ("platform", "category", "result"),
)

# --- Price ---
PRICE_OBS = _REG.counter(
    "mayabu_price_observations_total",
    "Price observation write outcomes",
    ("platform", "result"),
)

# --- Stock classification (bounded labels; no product/URL cardinality) ---
STOCK_CLASSIFICATION = _REG.counter(
    "mayabu_stock_classification_total",
    "Stock classifier outcomes by platform and public state",
    ("platform", "state"),
)
STOCK_UNCERTAIN = _REG.counter(
    "mayabu_stock_uncertain_total",
    "Ambiguous/uncertain stock classifications by platform",
    ("platform",),
)
STOCK_TRANSITION = _REG.counter(
    "mayabu_stock_transition_total",
    "Published stock transitions by platform",
    ("platform", "transition"),
)
STOCK_CONFIRMATION_RETRY = _REG.counter(
    "mayabu_stock_confirmation_retry_total",
    "Surprising OOS confirmation / preserve outcomes",
    ("platform", "result"),
)

# --- Enrichment / overlap (bounded labels) ---
ENRICHMENT_TOTAL = _REG.counter(
    "mayabu_enrichment_total",
    "Background enrich_listing outcomes",
    ("platform", "result"),
)
ENRICHMENT_DURATION = _REG.histogram(
    "mayabu_enrichment_duration_ms",
    "Background enrich_listing duration",
    ("platform",),
)
ENRICHMENT_GALLERY = _REG.histogram(
    "mayabu_enrichment_gallery_images",
    "Gallery images found during enrichment",
    ("platform",),
)
ENRICHMENT_MODEL = _REG.counter(
    "mayabu_enrichment_model_number_total",
    "Model number found during enrichment",
    ("platform", "result"),
)
SPEC_CONFLICT = _REG.counter(
    "mayabu_spec_conflict_total",
    "Spec merge conflicts during enrichment",
    ("category",),
)
OVERLAP_DISCOVERY = _REG.counter(
    "mayabu_overlap_discovery_total",
    "Targeted cross-retailer discovery outcomes",
    ("platform", "result"),
)

# --- User price verification (bounded labels only) ---
USER_PRICE_VERIFICATION = _REG.counter(
    "mayabu_user_price_verification_total",
    "User-triggered price verification request outcomes",
    ("result",),
)
USER_PRICE_VERIFICATION_DURATION = _REG.histogram(
    "mayabu_user_price_verification_duration_ms",
    "User price verification request orchestration latency",
    ("result",),
)
SCHEDULER_TICK = _REG.counter(
    "mayabu_scheduler_tick_total",
    "Scheduler tick outcomes",
    ("result",),
)
SCHEDULER_TASKS = _REG.counter(
    "mayabu_scheduler_tasks_created_total",
    "Tasks created by the scheduler",
    ("task_type",),
)
SCHEDULER_HEARTBEAT_AGE = _REG.gauge(
    "mayabu_scheduler_heartbeat_age_seconds",
    "Age of the automation scheduler heartbeat",
    (),
)
PRICE_SIGNAL = _REG.counter(
    "mayabu_price_signal_total",
    "Price-timing signal assignments",
    ("signal",),
)
HARD_CONFLICT = _REG.counter(
    "mayabu_hard_conflict_total",
    "Hard identity conflicts that blocked exact merge",
    ("category", "conflict_type"),
)
USER_PRICE_VERIFICATION_STORE = _REG.counter(
    "mayabu_user_price_verification_store_check_total",
    "Per-store outcomes for user-triggered verification jobs",
    ("platform", "result"),
)


def timer(histogram, **labels: str) -> Timer:
    return Timer(histogram, **labels)


def status_class(code: int) -> str:
    if code < 200:
        return "1xx"
    if code < 300:
        return "2xx"
    if code < 400:
        return "3xx"
    if code < 500:
        return "4xx"
    return "5xx"


def route_template(path: str) -> str:
    """Collapse high-cardinality path segments into templates."""
    parts = [p for p in (path or "").split("/") if p]
    out: list[str] = []
    for part in parts:
        if len(part) >= 32 or (len(part) >= 8 and all(ch in "0123456789abcdef-" for ch in part.lower())):
            out.append(":id")
        elif part.isdigit():
            out.append(":n")
        else:
            out.append(part[:40])
    return "/" + "/".join(out) if out else "/"


def refresh_pool_gauges(stats: dict | None) -> None:
    if not stats:
        return
    # psycopg_pool get_stats keys vary by version; accept common aliases.
    size = stats.get("pool_size") or stats.get("size") or stats.get("pool_max")
    used = stats.get("pool_available")
    # Some versions expose requests_waiting / pool_min
    waiting = stats.get("requests_waiting") or stats.get("waiting") or 0
    if size is not None:
        DB_POOL_SIZE.set(float(size))
    if used is not None and size is not None:
        # available means free; in-use ≈ size - available when both present
        try:
            DB_POOL_IN_USE.set(max(0.0, float(size) - float(used)))
        except (TypeError, ValueError):
            pass
    # Prefer explicit usage counters when present
    for key in ("pool_used", "used", "connections_num"):
        if key in stats:
            try:
                DB_POOL_IN_USE.set(float(stats[key]))
                break
            except (TypeError, ValueError):
                pass
    try:
        DB_POOL_WAITING.set(float(waiting))
    except (TypeError, ValueError):
        pass
