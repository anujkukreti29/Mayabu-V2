"""Quick local health check for Mayabu API connectivity."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = os.environ.get("MAYABU_API_BASE", "http://127.0.0.1:8000")


def check(path: str) -> tuple[int, str]:
    url = f"{DEFAULT_BASE.rstrip('/')}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - doctor must surface any failure
        return 0, str(exc)


def _warn_automation(health_body: str) -> None:
    try:
        payload = json.loads(health_body)
    except json.JSONDecodeError:
        return
    worker = payload.get("worker_status")
    if worker in {"none", "stale"}:
        print("  WARN Check latest price needs a worker: python worker_db.py --loop --concurrency 2")
    enabled = os.environ.get("MAYABU_SCHEDULER_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    scheduler = payload.get("scheduler") or {}
    if enabled and not scheduler.get("scheduler_alive"):
        print("  WARN automation enabled but scheduler heartbeat is stale: python -m mayabu.scheduler")


def main() -> int:
    print(f"Mayabu API doctor → {DEFAULT_BASE}")
    ok = True
    health_body = ""
    for path in ("/api/live", "/api/ready", "/api/health", "/api/homepage?limit=2", "/api/search?q=asus&limit=1"):
        status, body = check(path)
        preview = body.replace("\n", " ")[:160]
        mark = "OK" if status == 200 else "FAIL"
        if status != 200:
            ok = False
        print(f"  [{mark}] {status:>3} {path}  {preview}")
        if path == "/api/health" and status == 200:
            health_body = body
    if health_body:
        _warn_automation(health_body)
    if not ok:
        print("\nBackend is not healthy. Start Postgres/Redis, migrate, then:")
        print("  scripts\\start_api_windows.cmd")
        print("Frontend (separate terminal):")
        print("  cd frontend && npm run dev")
        print("Worker (Check latest price):")
        print("  python worker_db.py --loop --concurrency 2")
        print("Scheduler (optional, MAYABU_SCHEDULER_ENABLED=true):")
        print("  python -m mayabu.scheduler")
        return 1
    print("\nAll checks passed.")
    print("Worker: python worker_db.py --loop --concurrency 2")
    print("Scheduler: python -m mayabu.scheduler  (disabled unless MAYABU_SCHEDULER_ENABLED=true)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
