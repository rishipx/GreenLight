"""Telegram callback endpoint: operator approval or dismissal of an incident."""

import hmac
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from greenlight.core.privacy import callback_audit_metadata
from greenlight.core.security import ensure_operator, hash_token, verify_telegram_secret
from greenlight.db import get_db
from greenlight.db.models import Incident, IncidentAudit, RemediationJob
from greenlight.services import telegram
from greenlight.services.runbooks import is_allowlisted_runbook

logger = logging.getLogger("greenlight.api")
router = APIRouter(prefix="/api/v1/webhooks", tags=["telegram"])


async def _ack(callback_id: str, text: str, alert: bool = False) -> None:
    """Acknowledge a callback. A Telegram outage must not turn a committed decision into a 500."""
    try:
        await telegram.ack(callback_id, text, alert)
    except Exception:
        logger.exception("telegram ack failed")


async def _finalize_message(message: dict, badge: str) -> None:
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    if not (chat_id and message_id):
        return
    try:
        await telegram.finalize(chat_id, message_id, message.get("text", ""), badge)
    except Exception:
        logger.exception("telegram finalize failed")


def _claim_pending(db: Session, incident_id: str, new_status: str, now: datetime) -> bool:
    """Atomically move a PENDING, unused-token incident to ``new_status``; exactly one caller can win."""
    claimed = db.execute(
        update(Incident)
        .where(
            Incident.id == incident_id,
            Incident.status == "PENDING",
            Incident.approval_used_at.is_(None),
        )
        .values(status=new_status, approval_used_at=now, updated_at=now)
    ).rowcount
    if claimed != 1:
        db.rollback()
        return False
    return True


def _audit(incident_id: str, operator_id: int, action: str, details: dict) -> IncidentAudit:
    return IncidentAudit(incident_id=incident_id, actor_telegram_id=operator_id, action=action, details=details)


@router.post("/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    verify_telegram_secret(request)
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Invalid JSON body") from None
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid JSON body")
    callback = payload.get("callback_query")
    if not callback:
        return {"status": "ignored"}

    callback_id = callback.get("id", "")
    try:
        actor = int(callback.get("from", {}).get("id", 0))
    except (TypeError, ValueError):
        actor = 0
    data = callback.get("data", "")
    message = callback.get("message", {})

    try:
        operator = ensure_operator(db, actor)
    except HTTPException:
        await _ack(callback_id, "Unauthorized operator", True)
        logger.warning({"event": "security_rejected_callback", "actor": actor, "callback_id": callback_id})
        return {"status": "forbidden"}

    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] not in {"exec", "dsm"}:
        await _ack(callback_id, "Malformed or unknown action", True)
        return {"status": "bad_request"}

    action, incident_id, token = parts
    incident = db.get(Incident, incident_id)
    if not incident:
        await _ack(callback_id, "Incident not found", True)
        return {"status": "not_found"}

    if not incident.approval_token_hash or not hmac.compare_digest(incident.approval_token_hash, hash_token(token)):
        await _ack(callback_id, "Invalid approval token", True)
        logger.warning(
            {
                "event": "security_rejected_callback",
                "actor": actor,
                "incident_id": incident_id,
                "reason": "invalid_token",
            }
        )
        return {"status": "forbidden"}

    expires_at = incident.approval_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if not expires_at or expires_at < datetime.now(UTC):
        await _ack(callback_id, "Approval token expired", True)
        return {"status": "expired"}

    if incident.approval_used_at is not None:
        await _ack(callback_id, "Approval token already used", True)
        return {"status": "conflict"}

    now = datetime.now(UTC)
    audit_details = callback_audit_metadata(
        callback_id=callback_id,
        actor_telegram_id=operator.telegram_id,
        incident_id=incident_id,
        action="DISMISSED" if action == "dsm" else "APPROVED",
    )

    if action == "dsm":
        if not _claim_pending(db, incident_id, "DISMISSED", now):
            await _ack(callback_id, "Incident already resolved", True)
            return {"status": "conflict"}
        db.add(_audit(incident_id, operator.telegram_id, "DISMISSED", audit_details))
        db.commit()
        await _ack(callback_id, "Incident dismissed")
        await _finalize_message(message, "DISMISSED")
        return {"status": "success", "incident_id": incident_id, "action": "DISMISSED"}

    if not is_allowlisted_runbook(incident.remediation_key):
        db.add(
            _audit(
                incident_id,
                operator.telegram_id,
                "REJECTED",
                {
                    "incident_id": incident_id,
                    "reason": "no_allowlisted_remediation_key",
                    "requested_key": incident.remediation_key,
                },
            )
        )
        db.commit()
        await _ack(callback_id, "No allowlisted remediation is available", True)
        logger.warning({"event": "approval_rejected_no_recommendation", "actor": actor, "incident_id": incident_id})
        return {"status": "no_recommendation"}

    if not _claim_pending(db, incident_id, "EXECUTING", now):
        await _ack(callback_id, "Incident already resolved", True)
        return {"status": "conflict"}

    job = RemediationJob(
        incident_id=incident_id,
        remediation_key=incident.remediation_key,
        requested_by=operator.telegram_id,
    )
    db.add(job)
    db.add(_audit(incident_id, operator.telegram_id, "APPROVED", audit_details))
    db.commit()
    db.refresh(job)
    await _ack(callback_id, "Approved. Remediation queued.")
    await _finalize_message(message, "QUEUED FOR REMEDIATION")
    logger.info({"event": "remediation_approved", "incident_id": incident_id, "execution_id": job.id, "actor": actor})
    return {"status": "success", "incident_id": incident_id, "action": "QUEUED", "execution_id": job.id}
