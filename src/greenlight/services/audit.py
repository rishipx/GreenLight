"""Audit-trail rows: one constructor for every writer, and the metadata Telegram callbacks may persist."""

from typing import Any

from greenlight.db.models import IncidentAudit


def audit_entry(
    incident_id: str, actor_telegram_id: int, action: str, details: dict[str, Any] | None = None
) -> IncidentAudit:
    return IncidentAudit(incident_id=incident_id, actor_telegram_id=actor_telegram_id, action=action, details=details)


def callback_audit_metadata(
    *, callback_id: str, actor_telegram_id: int, action: str, incident_id: str
) -> dict[str, Any]:
    """Persist callback metadata only; never persist the Telegram approval token or raw update."""
    return {
        "callback_id": callback_id,
        "actor_telegram_id": actor_telegram_id,
        "action": action,
        "incident_id": incident_id,
    }
