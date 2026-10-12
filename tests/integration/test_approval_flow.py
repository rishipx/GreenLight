"""Telegram approval callbacks: authorization, replay protection and audit records."""

from greenlight.db import SessionLocal
from greenlight.db.models import Incident, IncidentAudit, RemediationJob
from tests.helpers import callback, client, create_incident, diagnosis, issue_token


def test_unauthorized_callback():
    payload = {
        "callback_query": {"id": "cb1", "from": {"id": 999}, "data": "exec:does-not-matter:badtoken", "message": {}}
    }
    r = client.post("/api/v1/webhooks/telegram", json=payload)
    assert r.status_code == 200 and r.json()["status"] == "forbidden"


def test_approval_queues_without_execution():
    incident = create_incident()
    iid = incident["id"]
    token = issue_token(iid)
    payload = {"callback_query": {"id": "cb2", "from": {"id": 123456789}, "data": f"exec:{iid}:{token}", "message": {}}}
    first = client.post("/api/v1/webhooks/telegram", json=payload)
    assert first.json()["status"] == "success" and first.json()["action"] == "QUEUED"
    with SessionLocal() as db:
        assert db.get(Incident, iid).status == "EXECUTING"
        assert db.query(RemediationJob).filter_by(incident_id=iid).count() == 1
        assert db.query(IncidentAudit).filter_by(incident_id=iid, action="APPROVED").count() == 1


def test_duplicate_approval_is_rejected():
    incident = create_incident()
    iid = incident["id"]
    token = issue_token(iid)
    payload = {"callback_query": {"id": "cb3", "from": {"id": 123456789}, "data": f"exec:{iid}:{token}", "message": {}}}
    assert client.post("/api/v1/webhooks/telegram", json=payload).json()["status"] == "success"
    second = client.post(
        "/api/v1/webhooks/telegram", json={**payload, "callback_query": {**payload["callback_query"], "id": "cb4"}}
    )
    assert second.json()["status"] == "conflict"


def test_concurrent_approval_only_one_wins():
    from concurrent.futures import ThreadPoolExecutor

    incident = create_incident()
    iid = incident["id"]
    token = issue_token(iid)

    def click(callback_id):
        payload = {
            "callback_query": {
                "id": callback_id,
                "from": {"id": 123456789},
                "data": f"exec:{iid}:{token}",
                "message": {},
            }
        }
        return client.post("/api/v1/webhooks/telegram", json=payload).json()["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(click, ["race-a", "race-b"]))
    assert sorted(results) == ["conflict", "success"]


def test_cannot_approve_incident_without_recommendation(monkeypatch):
    async def none_key(*a):
        return diagnosis(None)

    monkeypatch.setattr("greenlight.services.incidents.analyze", none_key)
    iid = create_incident()["id"]
    token = issue_token(iid)
    payload = {"callback_query": {"id": "nr1", "from": {"id": 123456789}, "data": f"exec:{iid}:{token}", "message": {}}}
    assert client.post("/api/v1/webhooks/telegram", json=payload).json()["status"] == "no_recommendation"
    with SessionLocal() as db:
        assert db.get(Incident, iid).status == "PENDING"
        assert db.query(RemediationJob).filter_by(incident_id=iid).count() == 0
    # the operator can still dismiss it with the same (unconsumed) token
    payload["callback_query"].update(id="nr2", data=f"dsm:{iid}:{token}")
    assert client.post("/api/v1/webhooks/telegram", json=payload).json()["action"] == "DISMISSED"


def test_telegram_audit_does_not_store_raw_approval_token():
    incident = create_incident()
    iid = incident["id"]
    token = issue_token(iid)
    payload = {
        "callback_query": {"id": "privacy-1", "from": {"id": 123456789}, "data": f"exec:{iid}:{token}", "message": {}}
    }
    assert client.post("/api/v1/webhooks/telegram", json=payload).json()["status"] == "success"
    with SessionLocal() as db:
        audit = db.query(IncidentAudit).filter_by(incident_id=iid, action="APPROVED").one()
        assert audit.details == {
            "callback_id": "privacy-1",
            "actor_telegram_id": 123456789,
            "action": "APPROVED",
            "incident_id": iid,
        }
        assert token not in str(audit.details)


def test_telegram_webhook_rejects_non_json_body():
    response = client.post(
        "/api/v1/webhooks/telegram", content=b"not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400


def test_callback_succeeds_even_if_telegram_ack_fails(monkeypatch):
    from greenlight.services import telegram

    async def failing(*args, **kwargs):
        raise RuntimeError("telegram unavailable")

    monkeypatch.setattr(telegram, "_call", failing)
    incident_id = create_incident()["id"]
    token = issue_token(incident_id)
    response = client.post("/api/v1/webhooks/telegram", json=callback("ack-fail", f"exec:{incident_id}:{token}"))
    assert response.status_code == 200 and response.json()["status"] == "success"
