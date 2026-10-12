"""PostgreSQL-only integration tests.

The SQLite suite in the SQLite suite proves application logic. SQLite ignores
FOR UPDATE SKIP LOCKED, so row-locking semantics are verified here against a real
PostgreSQL. Skipped unless TEST_POSTGRES_URL is set, e.g.

    TEST_POSTGRES_URL=postgresql+psycopg://greenlight:greenlight@localhost:5432/greenlight_test pytest tests/integration/test_postgres_locking.py
"""

import os
import threading

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

PG_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set")

from datetime import UTC

from greenlight.db import Base  # noqa: E402
from greenlight.db.models import Incident, IncidentAudit, Operator, RemediationJob  # noqa: E402
from greenlight.worker import claim_job, recover_stale_jobs  # noqa: E402


@pytest.fixture()
def pg():
    engine = create_engine(PG_URL, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add(Operator(telegram_id=5_000_000_000, role="ADMIN", enabled=True))  # > 2**31: needs BIGINT
        db.commit()
    yield Session
    engine.dispose()


def _queue_jobs(Session, n):
    ids = []
    with Session() as db:
        for _ in range(n):
            inc = Incident(service_name="svc", host_ip="10.0.0.1", error_trace="x" * 20, status="EXECUTING")
            db.add(inc)
            db.flush()
            job = RemediationJob(
                incident_id=inc.id, remediation_key="payment_gateway_restart", requested_by=5_000_000_000
            )
            db.add(job)
            db.flush()
            ids.append(job.id)
        db.commit()
    return ids


def test_concurrent_workers_never_claim_the_same_job(pg):
    n_jobs, n_workers = 12, 12
    _queue_jobs(pg, n_jobs)
    barrier = threading.Barrier(n_workers)
    claimed, errors = [], []

    def worker():
        try:
            with pg() as db:
                barrier.wait()
                job = claim_job(db)
                if job:
                    claimed.append(job.id)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(claimed) == n_jobs and len(set(claimed)) == n_jobs  # each job claimed exactly once


def test_more_workers_than_jobs_leaves_extras_idle_not_duplicated(pg):
    _queue_jobs(pg, 3)
    barrier = threading.Barrier(8)
    claimed = []

    def worker():
        with pg() as db:
            barrier.wait()
            job = claim_job(db)
            if job:
                claimed.append(job.id)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claimed) == 3 and len(set(claimed)) == 3


def test_skip_locked_skips_a_row_locked_by_another_transaction(pg):
    _queue_jobs(pg, 2)
    holder = pg()
    holder.execute(text("SELECT id FROM remediation_jobs ORDER BY created_at LIMIT 1 FOR UPDATE"))  # lock oldest row
    with pg() as other:
        job = claim_job(other)  # must not block and must not take the locked row
        assert job is not None
    holder.rollback()
    holder.close()
    with pg() as db:
        statuses = sorted(j.status for j in db.query(RemediationJob).all())
    assert statuses == ["QUEUED", "RUNNING"]


def test_stale_recovery_on_postgres(pg):
    from datetime import datetime, timedelta

    (jid,) = _queue_jobs(pg, 1)
    with pg() as db:
        j = db.get(RemediationJob, jid)
        j.status, j.attempt_count = "RUNNING", 1
        j.claimed_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
    with pg() as db:
        assert recover_stale_jobs(db) == 1
        assert db.get(RemediationJob, jid).status == "QUEUED"
        assert db.query(IncidentAudit).filter_by(action="JOB_REQUEUED").count() == 1
