"""Rate limiting and secret comparison."""

from greenlight.core.config import settings
from greenlight.core.security import SlidingWindowLimiter, issue_approval_token
from tests.helpers import client


def test_limiter_blocks_after_limit_and_is_per_key(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_requests", 2)
    limiter = SlidingWindowLimiter()
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")


def test_approval_token_fits_telegram_callback_limit():
    token, token_hash, _ = issue_approval_token()
    assert len(f"exec:{'x' * 36}:{token}".encode()) <= 64
    assert token not in token_hash and len(token_hash) == 64


def test_non_ascii_secret_is_rejected_not_a_server_error(monkeypatch):
    monkeypatch.setattr(settings, "ingest_api_key", "ingest-key")
    body = {"service_name": "worker", "host_ip": "10.0.0.10", "error_trace": "fatal worker exception occurred"}
    response = client.post(
        "/api/v1/incidents/ingest", json=body, headers={"X-GreenLight-API-Key": "caf\u00e9".encode("latin-1")}
    )
    assert response.status_code == 401
