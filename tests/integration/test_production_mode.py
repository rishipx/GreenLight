"""Fail-closed behavior when APP_ENV=production."""

import pytest
from fastapi.testclient import TestClient

from greenlight.main import app
from tests.helpers import client


def test_production_requires_complete_configuration(monkeypatch):
    from greenlight.core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    errors = settings.production_config_errors()
    assert (
        any("INGEST_API_KEY" in e for e in errors)
        and any("READ_API_KEY" in e for e in errors)
        and any("AGENT_WEBHOOK_SECRET" in e for e in errors)
    )
    with pytest.raises(RuntimeError), TestClient(app):
        pass


def test_production_rejects_unconfigured_webhooks_and_api(monkeypatch):
    from greenlight.core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    body = {"service_name": "worker", "host_ip": "10.0.0.10", "error_trace": "fatal worker exception occurred"}
    assert client.post("/api/v1/webhooks/agent", json=body).status_code == 503
    assert client.post("/api/v1/webhooks/generic", json={"message": "x" * 20}).status_code == 503
    assert client.post("/api/v1/incidents/ingest", json=body).status_code == 503
    assert client.get("/api/v1/incidents").status_code == 503
    assert client.post("/api/v1/webhooks/telegram", json={}).status_code == 503


def test_production_rejects_missing_api_keys_even_when_webhook_keys_are_set(monkeypatch):
    from greenlight.core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "telegram_bot_token", "bot")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "tg")
    monkeypatch.setattr(settings, "ingest_api_key", None)
    monkeypatch.setattr(settings, "read_api_key", None)
    monkeypatch.setattr(settings, "agent_webhook_secret", "agent")
    monkeypatch.setattr(settings, "alertmanager_webhook_secret", "alertmanager")
    monkeypatch.setattr(settings, "generic_webhook_secret", "generic")
    errors = settings.production_config_errors()
    assert any("INGEST_API_KEY" in e for e in errors)
    assert any("READ_API_KEY" in e for e in errors)
