"""Worker main loop: claim a job, run its allowlisted runbook, record the outcome."""

import asyncio
import logging
import time
from datetime import UTC, datetime

from greenlight.core.config import settings
from greenlight.db import SessionLocal, init_db
from greenlight.db.models import Incident, IncidentAudit
from greenlight.services.runbooks import execute
from greenlight.worker.job_queue import claim_job, recover_stale_jobs
from greenlight.worker.notifier import notify_n8n

logger = logging.getLogger("greenlight.worker")


def process_once() -> bool:
    """Process at most one queued job. Returns ``True`` if a job was claimed."""
    db = SessionLocal()
    try:
        recover_stale_jobs(db)
        job = claim_job(db)
        if not job:
            return False

        incident = db.get(Incident, job.incident_id)
        result = execute(job.remediation_key)
        succeeded = bool(result.get("success"))
        now = datetime.now(UTC)
        job.result = result
        job.completed_at = now
        job.claimed_at = None
        job.status = "SUCCEEDED" if succeeded else "FAILED"

        if incident:
            incident.execution_result = result
            incident.status = "EXECUTED" if succeeded else "FAILED"
            incident.updated_at = now
            db.add(
                IncidentAudit(
                    incident_id=incident.id,
                    actor_telegram_id=job.requested_by,
                    action="EXECUTED" if succeeded else "EXECUTION_FAILED",
                    details={"execution_id": job.id, "result": result},
                )
            )

        db.commit()
        if incident:
            asyncio.run(notify_n8n(incident, job, result))
        logger.info(
            "remediation completed",
            extra={"incident_id": job.incident_id, "execution_id": job.id, "success": succeeded},
        )
        return True
    except Exception:
        db.rollback()
        logger.exception("worker job failed")
        return False
    finally:
        db.close()


def run_forever() -> None:
    # Deliberately synchronous: process_once() calls asyncio.run() for the n8n notification,
    # which cannot be called from inside a running event loop.
    init_db()
    while True:
        if not process_once():
            time.sleep(settings.worker_poll_seconds)
