"""Telegram approval prompts."""

import asyncio
from types import SimpleNamespace

from greenlight.core.config import settings
from greenlight.services import telegram

INCIDENT = SimpleNamespace(id="abc", service_name="s", host_ip="h", severity="P1", root_cause="r", remediation_key=None)


def test_dispatch_notifies_every_admin(monkeypatch):
    sent = []

    async def fake_call(method, payload):
        sent.append(payload["chat_id"])
        return {"ok": True}

    monkeypatch.setattr(telegram, "_call", fake_call)
    monkeypatch.setattr(settings, "telegram_admin_ids", "222,111")
    asyncio.run(telegram.dispatch(INCIDENT, "tok"))
    assert sent == [111, 222]


def test_dispatch_failure_for_one_admin_does_not_block_others(monkeypatch):
    sent = []

    async def flaky(method, payload):
        if payload["chat_id"] == 111:
            raise RuntimeError("boom")
        sent.append(payload["chat_id"])

    monkeypatch.setattr(telegram, "_call", flaky)
    monkeypatch.setattr(settings, "telegram_admin_ids", "111,222")
    asyncio.run(telegram.dispatch(INCIDENT, "tok"))
    assert sent == [222]
