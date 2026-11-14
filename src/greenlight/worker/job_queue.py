"""Job claiming and stale-job recovery (PostgreSQL ``FOR UPDATE SKIP LOCKED`` row locking)."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from greenlight.core.config import settings
from greenlight.db.models import Incident, RemediationJob
from greenlight.services.audit import audit_entry

logger = logging.getLogger("greenlight.worker")


def claim_job(db: Session) -> RemediationJob | None:
    """Lock and mark the oldest queued job as RUNNING, or return ``None`` when the queue is empty."""
    job = db.execute(
        select(RemediationJob)
        .where(RemediationJob.status == "QUEUED")
        .order_by(RemediationJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    ).scalar_one_or_none()
    if not job:
        return None

    job.status = "RUNNING"
    job.claimed_at = datetime.now(UTC)
    job.attempt_count += 1
    db.commit()
    db.refresh(job)
    return job


def recover_stale_jobs(db: Session) -> int:
    """Recover jobs whose worker died after claiming them.

    A RUNNING job older than WORKER_LEASE_SECONDS has lost its worker. It is requeued until
    WORKER_MAX_ATTEMPTS is reached, then failed permanently. Runbooks must therefore be idempotent
    because a requeued job can run again.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.worker_lease_seconds)
    stale = (
        db.execute(
            select(RemediationJob)
            .where(
                RemediationJob.status == "RUNNING",
                RemediationJob.claimed_at.is_not(None),
                RemediationJob.claimed_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )

    for job in stale:
        if job.attempt_count < settings.worker_max_attempts:
            _requeue(db, job)
        else:
            _abandon(db, job)

    if stale:
        db.commit()
    return len(stale)


def _requeue(db: Session, job: RemediationJob) -> None:
    job.status = "QUEUED"
    job.claimed_at = None
    job.result = None
    job.completed_at = None
    details = {"execution_id": job.id, "attempt_count": job.attempt_count}
    db.add(audit_entry(job.incident_id, job.requested_by, "JOB_REQUEUED", details))
    logger.warning({"event": "job_requeued", "execution_id": job.id, "attempt_count": job.attempt_count})


def _abandon(db: Session, job: RemediationJob) -> None:
    now = datetime.now(UTC)
    result = {
        "success": False,
        "exit_code": -1,
        "stdout": "",
        "stderr": "Worker lease expired; max attempts exceeded",
    }
    job.status = "FAILED"
    job.result = result
    job.claimed_at = None
    job.completed_at = now
    incident = db.get(Incident, job.incident_id)
    if incident:
        incident.status = "FAILED"
        incident.execution_result = result
        incident.updated_at = now
    details = {"execution_id": job.id, "result": result}
    db.add(audit_entry(job.incident_id, job.requested_by, "EXECUTION_FAILED", details))
    logger.error({"event": "job_abandoned", "execution_id": job.id, "attempt_count": job.attempt_count})
