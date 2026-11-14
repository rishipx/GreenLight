"""Optional n8n completion notification."""

import logging

import httpx

from greenlight.core.config import settings
from greenlight.db.models import Incident, RemediationJob

logger = logging.getLogger("greenlight.worker")


async def notify_n8n(incident: Incident, job: RemediationJob, result: dict) -> None:
    if not settings.n8n_webhook_url:
        return
    payload = {
        "event": "INCIDENT_RESOLVED",
        "incident_id": incident.id,
        "execution_id": job.id,
        "action": "EXECUTED" if result.get("success") else "EXECUTION_FAILED",
        "resolved_by_admin": job.requested_by,
        "service": incident.service_name,
        "severity": incident.severity,
        "execution_summary": result,
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(settings.n8n_webhook_url, json=payload)
    except Exception:
        logger.exception("n8n notification failed", extra={"incident_id": incident.id, "execution_id": job.id})
