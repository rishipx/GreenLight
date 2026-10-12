"""Authentication, request protection, operator authorization and approval tokens."""

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from greenlight.core.config import settings
from greenlight.db.models import Operator

_MAX_TRACKED_RATE_KEYS = 10_000


class SlidingWindowLimiter:
    """In-process sliding-window rate limiter (single instance only)."""

    def __init__(self) -> None:
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - settings.rate_limit_window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= settings.rate_limit_requests:
                return False
            hits.append(now)
            if len(self._hits) > _MAX_TRACKED_RATE_KEYS:  # evict idle keys so memory stays bounded
                for stale in [k for k, v in self._hits.items() if not v or v[-1] < cutoff]:
                    del self._hits[stale]
            return True


limiter = SlidingWindowLimiter()


async def request_guard(request: Request) -> None:
    """Reject oversized bodies and clients that exceed the rate limit."""
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > settings.max_request_bytes:
                raise HTTPException(413, "Request body too large")
        except ValueError as exc:
            raise HTTPException(400, "Invalid Content-Length") from exc

    client = request.client.host if request.client else "unknown"
    if not limiter.allow(f"{request.url.path}:{client}"):
        raise HTTPException(429, "Rate limit exceeded")


def _supplied_secret(request: Request, header_name: str) -> str:
    supplied = request.headers.get(header_name, "")
    if supplied:
        return supplied
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _secrets_match(supplied: str, expected: str) -> bool:
    # Compare bytes: str comparison raises TypeError on non-ASCII input (which would surface as a 500).
    return hmac.compare_digest(supplied.encode(), expected.encode())


def _verify_shared_secret(
    request: Request, expected: str | None, header_name: str, unconfigured: str, invalid: str
) -> None:
    if not expected:
        if settings.is_production:
            raise HTTPException(503, unconfigured)
        return
    if not _secrets_match(_supplied_secret(request, header_name), expected):
        raise HTTPException(401, invalid)


def verify_api_key(request: Request, expected: str | None, purpose: str) -> None:
    _verify_shared_secret(
        request,
        expected,
        "X-GreenLight-API-Key",
        f"{purpose} authentication is not configured",
        f"Invalid {purpose} API key",
    )


def verify_ingest_secret(request: Request, expected: str | None, source: str) -> None:
    _verify_shared_secret(
        request,
        expected,
        "X-GreenLight-Webhook-Secret",
        f"{source} webhook secret is not configured",
        f"Invalid {source} webhook secret",
    )


def verify_telegram_secret(request: Request) -> None:
    if not settings.telegram_webhook_secret:
        if settings.is_production:
            raise HTTPException(503, "Telegram webhook secret is not configured")
        return
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not _secrets_match(supplied, settings.telegram_webhook_secret):
        raise HTTPException(403, "Invalid webhook secret")


def require_ingest_api(request: Request) -> None:
    verify_api_key(request, settings.ingest_api_key, "ingest")


def require_read_api(request: Request) -> None:
    verify_api_key(request, settings.read_api_key, "read")


def ensure_operator(db: Session, telegram_id: int) -> Operator:
    """Return the enabled operator for ``telegram_id``, bootstrapping configured admins on first use."""
    operator = db.get(Operator, telegram_id)
    if operator and operator.enabled and operator.role in {"ADMIN", "APPROVER"}:
        return operator
    if telegram_id in settings.admin_ids:
        operator = Operator(telegram_id=telegram_id, role="ADMIN", enabled=True)
        db.add(operator)
        db.commit()
        return operator
    raise HTTPException(403, "Operator is not authorized")


def seed_operators(db: Session) -> None:
    for telegram_id in settings.admin_ids:
        if not db.get(Operator, telegram_id):
            db.add(Operator(telegram_id=telegram_id, role="ADMIN", enabled=True))
    db.commit()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_approval_token() -> tuple[str, str, datetime]:
    """Create a single-use approval token; only its SHA-256 hash is ever stored."""
    token = secrets.token_urlsafe(12)
    expires = datetime.now(UTC) + timedelta(seconds=settings.approval_ttl_seconds)
    return token, hash_token(token), expires
