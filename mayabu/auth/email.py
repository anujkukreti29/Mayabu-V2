"""Outbound email abstraction for auth flows (console + Resend production)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Protocol

import httpx

from mayabu.core.config import get_app_settings
from mayabu.monitoring import instrumentation as metrics

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OutboundEmail:
    to: str
    subject: str
    text_body: str
    kind: str
    html_body: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, str] = field(default_factory=dict)


class EmailSender(Protocol):
    def send(self, message: OutboundEmail) -> bool: ...


class ConsoleEmailSender:
    """Development/test sender: logs content and keeps a bounded in-memory outbox."""

    def __init__(self, *, max_messages: int = 200) -> None:
        self._messages: list[OutboundEmail] = []
        self._lock = Lock()
        self._max = max(10, max_messages)

    def send(self, message: OutboundEmail) -> bool:
        with self._lock:
            self._messages.append(message)
            if len(self._messages) > self._max:
                self._messages = self._messages[-self._max :]
        logger.info(
            "auth_email_queued",
            extra={
                "event": "auth_email",
                "kind": message.kind,
                "to_domain": message.to.split("@")[-1] if "@" in message.to else "unknown",
                "subject": message.subject[:80],
            },
        )
        metrics.EMAIL_SEND.inc(type=message.kind, result="ok")
        return True

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()

    def latest(self, *, kind: str | None = None, to: str | None = None) -> OutboundEmail | None:
        with self._lock:
            for message in reversed(self._messages):
                if kind and message.kind != kind:
                    continue
                if to and message.to.lower() != to.lower():
                    continue
                return message
        return None

    def all(self) -> list[OutboundEmail]:
        with self._lock:
            return list(self._messages)


class NullEmailSender:
    """Refuse delivery — never claims email was sent."""

    def send(self, message: OutboundEmail) -> bool:
        logger.warning(
            "auth_email_provider_unconfigured",
            extra={"event": "auth_email", "kind": message.kind},
        )
        metrics.EMAIL_SEND.inc(type=message.kind, result="unconfigured")
        return False


class ResendEmailSender:
    """Production adapter for https://resend.com (HTTP API via httpx)."""

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._from = from_address.strip()
        self._timeout = max(2.0, float(timeout_seconds))

    def send(self, message: OutboundEmail) -> bool:
        if not self._api_key or not self._from:
            metrics.EMAIL_SEND.inc(type=message.kind, result="unconfigured")
            return False
        payload: dict[str, object] = {
            "from": self._from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text_body,
        }
        if message.html_body:
            payload["html"] = message.html_body
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            logger.warning(
                "auth_email_timeout",
                extra={"event": "auth_email", "kind": message.kind},
            )
            metrics.EMAIL_SEND.inc(type=message.kind, result="timeout")
            return False
        except Exception:
            logger.exception("auth_email_send_failed", extra={"event": "auth_email", "kind": message.kind})
            metrics.EMAIL_SEND.inc(type=message.kind, result="error")
            return False

        if response.status_code >= 500:
            logger.warning(
                "auth_email_provider_5xx",
                extra={"event": "auth_email", "kind": message.kind, "status": response.status_code},
            )
            metrics.EMAIL_SEND.inc(type=message.kind, result="provider_error")
            return False
        if response.status_code >= 400:
            logger.warning(
                "auth_email_provider_4xx",
                extra={"event": "auth_email", "kind": message.kind, "status": response.status_code},
            )
            metrics.EMAIL_SEND.inc(type=message.kind, result="rejected")
            return False
        metrics.EMAIL_SEND.inc(type=message.kind, result="ok")
        logger.info(
            "auth_email_sent",
            extra={
                "event": "auth_email",
                "kind": message.kind,
                "to_domain": message.to.split("@")[-1] if "@" in message.to else "unknown",
            },
        )
        return True


_OUTBOX = ConsoleEmailSender()


def get_email_outbox() -> ConsoleEmailSender:
    return _OUTBOX


def get_email_sender() -> EmailSender:
    settings = get_app_settings()
    provider = (settings.auth_email_provider or "console").strip().lower()
    if provider in {"console", "dev", "test", "memory"}:
        return _OUTBOX
    if provider in {"null", "none", "disabled"}:
        return NullEmailSender()
    if provider == "resend":
        if not settings.auth_email_api_key:
            logger.error(
                "auth_email_resend_missing_key",
                extra={"event": "auth_email"},
            )
            return NullEmailSender()
        return ResendEmailSender(
            api_key=settings.auth_email_api_key,
            from_address=settings.auth_email_from,
            timeout_seconds=settings.auth_email_timeout_seconds,
        )
    logger.error(
        "auth_email_unknown_provider",
        extra={"event": "auth_email", "provider": provider[:40]},
    )
    return NullEmailSender()
