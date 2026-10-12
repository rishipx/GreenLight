"""Shared helpers for the test suite."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from greenlight.core.security import issue_approval_token
from greenlight.db import SessionLocal
from greenlight.db.models import Incident, Operator, RemediationJob
from greenlight.main import app
from greenlight.schemas import TriageDiagnosis

ADMIN_ID = 123456789
client = TestClient(app)


def diagnosis(key):
    return TriageDiagnosis(
        root_cause="Connection pool exhausted",
        severity="P0",
        suggested_fix="Restart worker",
        remediation_key=key,
        confidence_score=0.9,
    )


def create_incident():
    r = client.post(
        "/api/v1/incidents/ingest",
        json={
            "service_name": "payment-gateway",
            "host_ip": "192.168.1.104",
            "severity": "P0",
            "error_trace": "TooManyConnectionsError: too many clients already connected",
        },
    )
    assert r.status_code == 201
    return r.json()


def issue_token(incident_id):
    """Replace the incident's approval token with one the test knows (only the hash is stored)."""
    with SessionLocal() as db:
        item = db.get(Incident, incident_id)
        token, token_hash, expires = issue_approval_token()
        item.approval_token_hash = token_hash
        item.approval_expires_at = expires
        db.commit()
    return token


def callback(callback_id, data, actor=ADMIN_ID):
    return {"callback_query": {"id": callback_id, "from": {"id": actor}, "data": data, "message": {}}}


def approve(incident_id, callback_id):
    token = issue_token(incident_id)
    body = client.post("/api/v1/webhooks/telegram", json=callback(callback_id, f"exec:{incident_id}:{token}")).json()
    assert body["action"] == "QUEUED"


def running_job(attempts, age_seconds):
    incident_id = create_incident()["id"]
    with SessionLocal() as db:
        if db.get(Operator, ADMIN_ID) is None:
            db.add(Operator(telegram_id=ADMIN_ID, role="ADMIN", enabled=True))
        db.get(Incident, incident_id).status = "EXECUTING"
        job = RemediationJob(
            incident_id=incident_id,
            remediation_key="payment_gateway_restart",
            requested_by=ADMIN_ID,
            status="RUNNING",
            attempt_count=attempts,
            claimed_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
        )
        db.add(job)
        db.commit()
        return incident_id, job.id
