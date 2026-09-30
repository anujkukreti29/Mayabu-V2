"""Send a synthetic staging alert if MAYABU_ALERT_WEBHOOK_URL is configured.

Does not invent credentials. Exit codes:
  0 = delivered (HTTP 2xx)
  2 = NOT_CONFIGURED (no webhook)
  1 = delivery failed
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def main() -> int:
    url = (os.getenv("MAYABU_ALERT_WEBHOOK_URL") or "").strip()
    if not url:
        print(
            json.dumps(
                {
                    "status": "NOT_CONFIGURED",
                    "message": "Set MAYABU_ALERT_WEBHOOK_URL to a Slack/PagerDuty/generic webhook",
                }
            )
        )
        return 2

    payload = {
        "text": (
            f"[Mayabu staging synthetic alert] {datetime.now(timezone.utc).isoformat()} "
            f"env={os.getenv('MAYABU_ENV', 'unknown')} — ignore if intentional."
        ),
        "source": "mayabu.scripts.send_staging_alert",
        "severity": "warning",
        "synthetic": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "mayabu-alert-test/1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()[:200]
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "http_status": getattr(resp, "status", None),
                        "body_preview_len": len(body),
                    }
                )
            )
            return 0
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": "FAILED", "http_status": exc.code, "reason": str(exc.reason)}))
        return 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "FAILED", "error": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
