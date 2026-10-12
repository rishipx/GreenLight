"""Redaction of data sent to the LLM provider."""

from greenlight.schemas import Severity


def test_llm_redaction_removes_common_secrets_and_pii(monkeypatch):
    from greenlight.core import privacy

    raw = (
        "Authorization: Bearer super-secret-token-12345\n"
        'password=hunter2 token="tok-456"\n'
        "email=alice@example.com\n"
        "JWT=eyJabcdefghijk.abcdefghijklmnopqrstuvwxyz.1234567890\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        "https://user:password@example.com/api?api_key=secret-query\n"
        "-----BEGIN PRIVATE KEY-----\nsecret-material\n-----END PRIVATE KEY-----\n"
    )
    monkeypatch.setattr(privacy.settings, "llm_redaction_enabled", True)
    redacted = privacy.redact_for_llm(raw)
    assert "super-secret-token-12345" not in redacted
    assert "hunter2" not in redacted
    assert "alice@example.com" not in redacted
    assert "eyJabcdefghijk" not in redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "secret-query" not in redacted
    assert "secret-material" not in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_llm_redaction_sanitizes_structured_request_body(monkeypatch):
    from greenlight.core import privacy

    raw = (
        'Request body:\n{"user":{"email":"bob@example.com","name":"Bob"},"password":"top-secret","error":"queue full"}'
    )
    monkeypatch.setattr(privacy.settings, "llm_redaction_enabled", True)
    monkeypatch.setattr(privacy.settings, "llm_redact_request_bodies", True)
    redacted = privacy.redact_for_llm(raw)
    assert "top-secret" not in redacted
    assert "bob@example.com" not in redacted
    assert '"name":"Bob"' in redacted
    assert '"error":"queue full"' in redacted


def test_llm_redaction_sanitizes_trace_before_provider_call(monkeypatch):
    import asyncio
    import sys
    import types

    from greenlight.core.config import settings
    from greenlight.services import triage

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "http://llm.test/v1")
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured["messages"] = kwargs["messages"]
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(
                            content='{"root_cause":"Queue saturated","severity":"P1","suggested_fix":"Inspect workers","remediation_key":null,"confidence_score":0.0}'
                        )
                    )
                ]
            )

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    fake_openai = types.SimpleNamespace(AsyncOpenAI=FakeClient)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    trace = "password=top-secret email=alice@example.com Authorization: Bearer bearer-secret"
    diagnosis = asyncio.run(triage.analyze("svc", "10.0.0.10", trace, Severity.P1))
    assert diagnosis.remediation_key is None
    user_content = captured["messages"][1]["content"]
    assert "top-secret" not in user_content
    assert "alice@example.com" not in user_content
    assert "bearer-secret" not in user_content
