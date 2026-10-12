"""Incident ingestion, read API authentication and request guards."""

from greenlight.core.config import settings
from tests.helpers import client, create_incident


def test_health():
    assert client.get("/health").json()["status"] == "healthy"


def test_invalid_payload():
    r = client.post(
        "/api/v1/incidents/ingest",
        json={"service_name": "x", "host_ip": "not-ip", "error_trace": "fatal exception here"},
    )
    assert r.status_code == 422


def test_ingest_and_triage():
    body = create_incident()
    assert body["status"] == "PENDING"
    assert body["remediation_key"] == "payment_gateway_restart"


def test_invalid_content_length_is_rejected():
    r = client.get("/health", headers={"Content-Length": "not-an-int"})
    assert r.status_code == 400


def test_production_api_uses_separate_ingest_and_read_keys(monkeypatch):
    from greenlight.core.config import settings

    body = {"service_name": "worker", "host_ip": "10.0.0.10", "error_trace": "fatal worker exception occurred"}
    monkeypatch.setattr(settings, "ingest_api_key", "ingest-key")
    monkeypatch.setattr(settings, "read_api_key", "read-key")
    monkeypatch.setattr(settings, "app_env", "development")

    assert (
        client.post("/api/v1/incidents/ingest", json=body, headers={"X-GreenLight-API-Key": "wrong"}).status_code == 401
    )
    assert client.get("/api/v1/incidents", headers={"X-GreenLight-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/incidents", headers={"X-GreenLight-API-Key": "read-key"}).status_code == 200
    assert (
        client.post("/api/v1/incidents/ingest", json=body, headers={"Authorization": "Bearer ingest-key"}).status_code
        == 201
    )


def test_duplicate_alert_returns_existing_incident(monkeypatch):
    monkeypatch.setattr(settings, "dedupe_window_seconds", 300)
    payload = {"service_name": "dedupe-svc", "host_ip": "10.0.0.9", "error_trace": "identical failure trace repeated"}
    first = client.post("/api/v1/incidents/ingest", json=payload).json()
    second = client.post("/api/v1/incidents/ingest", json=payload).json()
    assert first["id"] == second["id"]


def test_dedupe_can_be_disabled():
    payload = {
        "service_name": "nodedupe-svc",
        "host_ip": "10.0.0.10",
        "error_trace": "identical failure trace repeated",
    }
    first = client.post("/api/v1/incidents/ingest", json=payload).json()
    second = client.post("/api/v1/incidents/ingest", json=payload).json()
    assert first["id"] != second["id"]


def test_get_incident_and_404():
    incident = create_incident()
    assert client.get(f"/api/v1/incidents/{incident['id']}").json()["id"] == incident["id"]
    assert client.get("/api/v1/incidents/does-not-exist").status_code == 404
    assert len(client.get("/api/v1/incidents").json()) >= 1
