"""Worker execution, stale-job recovery and the main loop."""

import pytest

from greenlight.db import SessionLocal
from greenlight.db.models import Incident, IncidentAudit, RemediationJob
from greenlight.worker import process_once
from tests.helpers import approve, client, create_incident, issue_token, running_job


def test_worker_executes_queued_job():
    incident = create_incident()
    iid = incident["id"]
    token = issue_token(iid)
    payload = {"callback_query": {"id": "cb5", "from": {"id": 123456789}, "data": f"exec:{iid}:{token}", "message": {}}}
    assert client.post("/api/v1/webhooks/telegram", json=payload).json()["action"] == "QUEUED"
    for _ in range(10):
        process_once()
        with SessionLocal() as db:
            if db.get(Incident, iid).status in {"EXECUTED", "FAILED"}:
                break
    with SessionLocal() as db:
        assert db.get(Incident, iid).status == "EXECUTED"
        job = db.query(RemediationJob).filter_by(incident_id=iid).one()
        assert job.status == "SUCCEEDED"
        assert db.query(IncidentAudit).filter_by(incident_id=iid, action="EXECUTED").count() == 1


def test_stale_running_job_is_requeued_then_completed():
    from greenlight.worker import recover_stale_jobs

    iid, jid = running_job(attempts=1, age_seconds=10_000)
    with SessionLocal() as db:
        assert recover_stale_jobs(db) == 1
        assert db.get(RemediationJob, jid).status == "QUEUED"
        assert db.query(IncidentAudit).filter_by(incident_id=iid, action="JOB_REQUEUED").count() == 1
    for _ in range(20):  # earlier tests may have left QUEUED jobs ahead of this one
        process_once()
        with SessionLocal() as db:
            if db.get(RemediationJob, jid).status == "SUCCEEDED":
                break
    with SessionLocal() as db:
        job = db.get(RemediationJob, jid)
        assert job.status == "SUCCEEDED" and job.attempt_count == 2
        assert db.get(Incident, iid).status == "EXECUTED"


def test_fresh_running_job_is_left_alone():
    from greenlight.worker import recover_stale_jobs

    _, jid = running_job(attempts=1, age_seconds=1)
    with SessionLocal() as db:
        assert recover_stale_jobs(db) == 0
        assert db.get(RemediationJob, jid).status == "RUNNING"
        db.get(RemediationJob, jid).status = "SUCCEEDED"
        db.commit()


def test_stale_job_over_max_attempts_fails_permanently():
    from greenlight.core.config import settings
    from greenlight.worker import recover_stale_jobs

    iid, jid = running_job(attempts=settings.worker_max_attempts, age_seconds=10_000)
    with SessionLocal() as db:
        assert recover_stale_jobs(db) == 1
        assert db.get(RemediationJob, jid).status == "FAILED"
        assert db.get(Incident, iid).status == "FAILED"
        assert db.query(IncidentAudit).filter_by(incident_id=iid, action="EXECUTION_FAILED").count() == 1


class _StopLoop(Exception):
    """Raised from a patched time.sleep to break out of run_forever()."""


def test_run_forever_is_a_plain_function():
    # process_once() calls asyncio.run(); an `async def` run_forever would run it inside an
    # event loop and raise "asyncio.run() cannot be called from a running event loop".
    import inspect

    from greenlight.worker import run_forever

    assert not inspect.iscoroutinefunction(run_forever)


def test_run_forever_processes_queued_job_and_notifies(monkeypatch, caplog):
    from greenlight.worker import loop as worker

    iid = create_incident()["id"]
    approve(iid, "loop-1")

    notified = []

    async def fake_notify(incident, job, result):
        notified.append(incident.id)

    def stop_when_idle(_seconds):
        raise _StopLoop

    monkeypatch.setattr(worker, "notify_n8n", fake_notify)
    monkeypatch.setattr(worker.time, "sleep", stop_when_idle)

    with caplog.at_level("ERROR"), pytest.raises(_StopLoop):
        worker.run_forever()

    with SessionLocal() as db:
        assert db.get(Incident, iid).status == "EXECUTED"
        assert db.query(RemediationJob).filter_by(incident_id=iid).one().status == "SUCCEEDED"
    assert iid in notified
    assert "worker job failed" not in caplog.text


def test_run_forever_sleeps_when_queue_is_empty(monkeypatch):
    from greenlight.worker import loop as worker

    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        raise _StopLoop

    monkeypatch.setattr(worker, "process_once", lambda: False)
    monkeypatch.setattr(worker.time, "sleep", fake_sleep)
    with pytest.raises(_StopLoop):
        worker.run_forever()
    assert sleeps == [worker.settings.worker_poll_seconds]
