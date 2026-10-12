"""LLM triage: fail-closed behavior and the runbook allowlist."""

from greenlight.schemas import Severity
from greenlight.services.triage import sanitize_diagnosis
from tests.helpers import diagnosis


def test_no_llm_key_yields_no_recommendation(monkeypatch):
    import asyncio

    from greenlight.core.config import settings
    from greenlight.services import triage

    monkeypatch.setattr(settings, "llm_api_key", None)
    d = asyncio.run(triage.analyze("redis-worker", "10.0.0.5", "queue latency high everywhere", Severity.P0))
    assert d.remediation_key is None and d.confidence_score == 0.0 and d.severity == Severity.P0


def test_key_outside_allowlist_is_rejected():
    d = sanitize_diagnosis(diagnosis("rm_rf_everything"))
    assert d.remediation_key is None and d.confidence_score == 0.0
    assert sanitize_diagnosis(diagnosis("redis_worker_restart")).remediation_key == "redis_worker_restart"


def test_llm_failure_degrades_to_no_recommendation(monkeypatch):
    import asyncio

    from greenlight.core.config import settings
    from greenlight.services import triage

    monkeypatch.setattr(settings, "llm_api_key", "dummy")
    monkeypatch.setattr(settings, "llm_base_url", "http://127.0.0.1:1/v1")  # connection refused
    d = asyncio.run(triage.analyze("svc", "10.0.0.5", "something broke badly"))
    assert d.remediation_key is None
