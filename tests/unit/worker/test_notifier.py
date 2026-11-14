"""The n8n completion notifier and the example workflow that consumes its payload."""

import asyncio
import json
import re

import httpx
import pytest

from greenlight.core.config import settings
from greenlight.db.models import Incident, RemediationJob
from greenlight.worker import notifier
from tests.paths import ENV_EXAMPLE, N8N_WORKFLOW

URL = "http://n8n:5678/webhook/greenlight"


def _records():
    incident = Incident(id="inc-1", service_name="payment-gateway", host_ip="10.0.0.1", error_trace="x", severity="P0")
    job = RemediationJob(id="job-1", incident_id="inc-1", remediation_key="payment_gateway_restart", requested_by=42)
    return incident, job


@pytest.fixture()
def posts(monkeypatch):
    """Replace the HTTP client; the returned list records every (url, json) POST."""
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def post(self, url, json):
            calls.append((url, json))

    monkeypatch.setattr(notifier.httpx, "AsyncClient", FakeClient)
    return calls


def _expected(action, result):
    return {
        "event": "INCIDENT_RESOLVED",
        "incident_id": "inc-1",
        "execution_id": "job-1",
        "action": action,
        "resolved_by_admin": 42,
        "service": "payment-gateway",
        "severity": "P0",
        "execution_summary": result,
    }


def test_nothing_is_sent_when_n8n_is_not_configured(monkeypatch, posts):
    monkeypatch.setattr(settings, "n8n_webhook_url", None)
    asyncio.run(notifier.notify_n8n(*_records(), {"success": True}))
    assert posts == []


def test_successful_run_is_posted_as_executed(monkeypatch, posts):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    result = {"success": True, "exit_code": 0}
    asyncio.run(notifier.notify_n8n(*_records(), result))
    assert posts == [(URL, _expected("EXECUTED", result))]


def test_failed_run_is_posted_as_execution_failed(monkeypatch, posts):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    result = {"success": False, "exit_code": 1}
    asyncio.run(notifier.notify_n8n(*_records(), result))
    assert posts == [(URL, _expected("EXECUTION_FAILED", result))]


def test_unreachable_n8n_never_breaks_the_worker(monkeypatch, posts):
    async def unreachable(self, url, json):
        raise httpx.ConnectError("n8n is down")

    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    monkeypatch.setattr(notifier.httpx.AsyncClient, "post", unreachable)
    asyncio.run(notifier.notify_n8n(*_records(), {"success": True}))  # must not raise


def test_example_workflow_matches_the_payload_the_notifier_sends(monkeypatch, posts):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    asyncio.run(notifier.notify_n8n(*_records(), {"success": True}))
    payload_fields = set(posts[0][1])

    raw = N8N_WORKFLOW.read_text()
    workflow = json.loads(raw)
    names = {node["name"] for node in workflow["nodes"]}
    webhook = next(node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.webhook")
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert URL.endswith("/webhook/" + webhook["parameters"]["path"])
    for source, outputs in workflow["connections"].items():
        assert source in names
        for branch in outputs["main"]:
            assert {link["node"] for link in branch} <= names
    # Every field the workflow reads must actually be sent by the notifier.
    assert set(re.findall(r"\$json\.body\.(\w+)", raw)) <= payload_fields
    assert f"N8N_WEBHOOK_URL={URL}" in ENV_EXAMPLE.read_text()
