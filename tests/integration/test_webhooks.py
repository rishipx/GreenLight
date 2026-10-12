"""Agent, Alertmanager and generic webhook authentication and normalization."""

from tests.helpers import client


def test_agent_webhook_requires_secret_when_configured(monkeypatch):
    from greenlight.core.config import settings

    monkeypatch.setattr(settings, "agent_webhook_secret", "agent-secret")
    payload = {"service_name": "worker", "host_ip": "10.0.0.10", "error_trace": "fatal worker exception occurred"}
    assert client.post("/api/v1/webhooks/agent", json=payload).status_code == 401
    r = client.post("/api/v1/webhooks/agent", json=payload, headers={"X-GreenLight-Webhook-Secret": "agent-secret"})
    assert r.status_code == 201 and r.json()["source"] == "linux-agent"
    monkeypatch.setattr(settings, "agent_webhook_secret", None)


def test_alertmanager_webhook_normalizes_firing_alerts(monkeypatch):
    from greenlight.core.config import settings

    monkeypatch.setattr(settings, "alertmanager_webhook_secret", "am-secret")
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighErrorRate",
                    "service": "checkout",
                    "severity": "critical",
                    "instance": "10.0.0.22:9100",
                },
                "annotations": {"summary": "HTTP 5xx spike", "description": "Error rate exceeded threshold"},
            },
            {"status": "resolved", "labels": {"alertname": "OldAlert", "service": "ignored"}},
        ]
    }
    r = client.post("/api/v1/webhooks/alertmanager", json=payload, headers={"Authorization": "Bearer am-secret"})
    assert r.status_code == 201 and len(r.json()) == 1
    assert r.json()[0]["source"] == "alertmanager"
    assert r.json()[0]["service_name"] == "checkout"
    monkeypatch.setattr(settings, "alertmanager_webhook_secret", None)


def test_generic_webhook_normalizes_common_observability_shape(monkeypatch):
    from greenlight.core.config import settings

    monkeypatch.setattr(settings, "generic_webhook_secret", "generic-secret")
    payload = {
        "service": "redis-worker",
        "host": "worker-01",
        "severity": "P2",
        "message": "queue latency above threshold",
    }
    r = client.post("/api/v1/webhooks/generic", json=payload, headers={"X-GreenLight-Webhook-Secret": "generic-secret"})
    assert r.status_code == 201
    body = r.json()
    assert body["source"] == "generic-webhook" and body["service_name"] == "redis-worker"
    assert body["host_ip"] == "worker-01"
    monkeypatch.setattr(settings, "generic_webhook_secret", None)


def test_alertmanager_skips_malformed_alert_but_keeps_the_rest():
    payload = {
        "alerts": [
            {"status": "firing", "labels": {"alertname": "x", "service": "a"}},  # service name too short
            {
                "status": "firing",
                "labels": {"alertname": "HighLatency", "service": "checkout"},
                "annotations": {"summary": "p99 latency above threshold"},
            },
        ]
    }
    response = client.post("/api/v1/webhooks/alertmanager", json=payload)
    assert response.status_code == 201
    assert [i["service_name"] for i in response.json()] == ["checkout"]


def test_generic_webhook_with_unusable_payload_is_a_422_not_a_500():
    assert client.post("/api/v1/webhooks/generic", json={"message": "short"}).status_code == 422
