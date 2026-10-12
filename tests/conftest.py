"""Test environment. Runs before any test module imports ``greenlight``, so settings pick this up."""

import os

os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_greenlight.db")
os.environ["TELEGRAM_ADMIN_IDS"] = "123456789"
os.environ["REMEDIATION_MODE"] = "dry-run"
os.environ["APPROVAL_TTL_SECONDS"] = "300"
os.environ["APP_ENV"] = "development"
os.environ["DEDUPE_WINDOW_SECONDS"] = "0"  # tests create many identical incidents; dedupe has its own tests
os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)

import contextlib

import pytest  # noqa: E402

from greenlight.db import Base, engine  # noqa: E402
from tests.helpers import diagnosis  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()
    if engine.url.get_backend_name() == "sqlite" and engine.url.database:
        with contextlib.suppress(OSError):
            os.remove(engine.url.database)


@pytest.fixture(autouse=True)
def stub_triage(monkeypatch):
    """Deterministic triage for tests that need a valid recommendation (no network)."""

    async def fake(service_name, host_ip, error_trace, source_severity=None):
        return diagnosis("payment_gateway_restart")

    monkeypatch.setattr("greenlight.services.incidents.analyze", fake)
