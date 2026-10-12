"""Incident creation: de-duplication, triage, persistence and operator notification."""

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from greenlight.core.config import settings
from greenlight.core.security import issue_approval_token
from greenlight.db.models import Incident
from greenlight.schemas import CrashReport
from greenlight.services import telegram
from greenlight.services.triage import analyze

logger = logging.getLogger("greenlight.incidents")


def find_duplicate(report: CrashReport, db: Session) -> Incident | None:
    """Return a recent PENDING incident with the identical service, host and trace, if dedupe is enabled."""
    window = settings.dedupe_window_seconds
    if window <= 0:
        return None
    cutoff = datetime.now(UTC) - timedelta(seconds=window)
    return (
        db.query(Incident)
        .filter(
            Incident.status == "PENDING",
            Incident.created_at >= cutoff,
            Incident.service_name == report.service_name,
            Incident.host_ip == report.host_ip,
            Incident.error_trace == report.error_trace,
        )
        .order_by(Incident.created_at.desc())
        .first()
    )


async def create_incident(report: CrashReport, db: Session, source: str) -> Incident:
    started = time.perf_counter()
    duplicate = find_duplicate(report, db)
    if duplicate:
        logger.info({"event": "incident_deduplicated", "incident_id": duplicate.id, "source": source})
        return duplicate

    diagnosis = await analyze(report.service_name, report.host_ip, report.error_trace, report.severity)
    token, token_hash, expires = issue_approval_token()
    incident = Incident(
        service_name=report.service_name,
        host_ip=report.host_ip,
        source=source,
        severity=diagnosis.severity.value,
        error_trace=report.error_trace,
        root_cause=diagnosis.root_cause,
        suggested_fix=diagnosis.suggested_fix,
        remediation_key=diagnosis.remediation_key,
        confidence_score=diagnosis.confidence_score,
        status="PENDING",
        approval_token_hash=token_hash,
        approval_expires_at=expires,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    await telegram.dispatch(incident, token)
    logger.info(
        {
            "event": "incident_ingested",
            "incident_id": incident.id,
            "service": incident.service_name,
            "source": source,
            "severity": incident.severity,
            "triage_latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    )
    return incident
