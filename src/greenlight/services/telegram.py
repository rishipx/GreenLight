"""Telegram Bot API client: approval prompts, callback acknowledgements and message updates."""

import html
import logging

import httpx

from greenlight.core.config import settings

logger = logging.getLogger("greenlight.telegram")


async def _call(method: str, payload: dict) -> dict:
    if not settings.telegram_bot_token:
        return {"ok": True, "mock": True}
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def _message_text(incident) -> str:
    if incident.remediation_key:
        footer = (
            f"<i>Human approval required. Token expires in {settings.approval_ttl_seconds}s. "
            f"Mode: {html.escape(settings.remediation_mode)}</i>"
        )
    else:
        footer = "<i>No automated remediation available. Manual investigation required.</i>"
    return (
        f"<b>GREENLIGHT INCIDENT [{incident.severity}]</b>\n\n"
        f"<b>Service:</b> <code>{html.escape(incident.service_name)}</code>\n"
        f"<b>Host:</b> <code>{html.escape(incident.host_ip)}</code>\n\n"
        f"<b>Root cause</b>\n{html.escape(incident.root_cause or 'Pending')}\n\n"
        f"<b>Proposed runbook</b>\n<code>{html.escape(incident.remediation_key or 'none')}</code>\n\n"
        f"{footer}"
    )


async def _dispatch_to(chat_id: int, incident, approval_token: str) -> dict:
    buttons = [{"text": "Dismiss", "callback_data": f"dsm:{incident.id}:{approval_token}"}]
    if incident.remediation_key:
        buttons.insert(0, {"text": "Approve & Queue", "callback_data": f"exec:{incident.id}:{approval_token}"})
    return await _call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": _message_text(incident),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [buttons]},
        },
    )


async def dispatch(incident, approval_token: str) -> list[dict]:
    """Send the approval prompt to every configured admin; the first valid click wins.

    A delivery failure for one admin is logged and does not prevent delivery to the others.
    """
    results = []
    for admin_id in sorted(settings.admin_ids) or [0]:
        try:
            results.append(await _dispatch_to(admin_id, incident, approval_token))
        except Exception:
            logger.exception("telegram dispatch failed", extra={"admin_id": admin_id, "incident_id": incident.id})
    return results


async def ack(callback_id: str, text: str, alert: bool = False) -> dict:
    return await _call(
        "answerCallbackQuery",
        {"callback_query_id": callback_id, "text": text, "show_alert": alert},
    )


async def finalize(chat_id: int, message_id: int, original_text: str, badge: str) -> dict:
    return await _call(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": f"{original_text}\n\n<b>Status:</b> {badge}",
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": []},
        },
    )
