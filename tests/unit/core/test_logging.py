"""Structured logging."""

import asyncio
import json
import logging

import httpx

from greenlight.core.config import settings
from greenlight.core.logging_config import JsonFormatter, configure_logging
from greenlight.services import telegram


def test_extra_fields_are_included_in_json_logs():
    record = logging.getLogger("t").makeRecord(
        "t", logging.ERROR, __file__, 1, "boom", (), None, extra={"incident_id": "abc"}
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["incident_id"] == "abc" and payload["message"] == "boom"


def test_telegram_bot_token_never_logged(monkeypatch, capsys):
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:SECRETTOKEN")
    real_client = httpx.AsyncClient

    class MockClient(real_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)
    configure_logging()
    asyncio.run(telegram._call("sendMessage", {"chat_id": 1, "text": "x"}))
    assert "SECRETTOKEN" not in capsys.readouterr().out
