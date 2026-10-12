"""Redaction of credentials and personal data before incident text is sent to an LLM provider."""

import json
import re
from typing import Any

from greenlight.core.config import settings

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
BEARER_RE = re.compile(r"(\bBearer\s+)[A-Za-z0-9._~+\-/]+=*", re.IGNORECASE)
BASIC_RE = re.compile(r"(\bBasic\s+)[A-Za-z0-9+/=]{8,}", re.IGNORECASE)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
GITHUB_TOKEN_RE = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")
SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
URL_CREDENTIAL_RE = re.compile(r"(https?://)([^:/\s]+):([^@/\s]+)@", re.IGNORECASE)
PEM_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*(?:PRIVATE KEY|CERTIFICATE|RSA PRIVATE KEY|EC PRIVATE KEY)[A-Z0-9 ]*-----.*?-----END [A-Z0-9 ]*(?:PRIVATE KEY|CERTIFICATE|RSA PRIVATE KEY|EC PRIVATE KEY)[A-Z0-9 ]*-----",
    re.IGNORECASE | re.DOTALL,
)
AUTH_HEADER_RE = re.compile(
    r"(?im)^(\s*(?:authorization|proxy-authorization|x-api-key|x-auth-token|x-access-token|cookie|set-cookie)\s*:\s*)[^\n]+$"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret|token|password|passwd|pwd|client[_-]?secret|access[_-]?token|refresh[_-]?token|session[_-]?token|private[_-]?key|credential)\b\s*[:=]\s*)([`\"']?)[^\s,;`\"'}]+\2"
)
SENSITIVE_QUERY_RE = re.compile(
    r"(?i)([?&](?:api[_-]?key|token|secret|password|access[_-]?token|refresh[_-]?token)=)[^&#\s]+"
)
SENSITIVE_KEY_RE = re.compile(
    r"(?i)(?:^|[_-])(?:api[_-]?key|secret|token|password|passwd|pwd|client[_-]?secret|access[_-]?token|refresh[_-]?token|session[_-]?token|private[_-]?key|authorization|cookie|set-cookie|credential|request[_-]?body|body)(?:$|[_-])"
)
REQUEST_BODY_MARKER = "Request body:\n"


_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "passwd",
        "pwd",
        "client_secret",
        "access_token",
        "refresh_token",
        "session_token",
        "private_key",
        "authorization",
        "cookie",
        "set-cookie",
        "credential",
        "request_body",
        "body",
        "email",
        "phone",
        "phone_number",
        "mobile",
        "address",
        "street",
        "ssn",
        "social_security_number",
        "date_of_birth",
        "dob",
    }
)


def _is_sensitive_key(key: str) -> bool:
    normalized = str(key).strip().lower()
    return normalized in _SENSITIVE_KEYS or bool(SENSITIVE_KEY_RE.search(normalized))


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _is_sensitive_key(str(key)) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _redact_request_body(raw: str) -> str:
    if not settings.llm_redact_request_bodies:
        return redact_text(raw)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return "[REDACTED_REQUEST_BODY]"
    return json.dumps(_redact_value(parsed), sort_keys=True, separators=(",", ":"), default=str)


def redact_text(text: str) -> str:
    value = str(text)
    value = PEM_RE.sub("[REDACTED_KEY_MATERIAL]", value)
    value = AUTH_HEADER_RE.sub(r"\1[REDACTED]", value)
    value = BEARER_RE.sub(r"\1[REDACTED]", value)
    value = BASIC_RE.sub(r"\1[REDACTED]", value)
    value = JWT_RE.sub("[REDACTED_JWT]", value)
    value = OPENAI_KEY_RE.sub("[REDACTED_API_KEY]", value)
    value = AWS_ACCESS_KEY_RE.sub("[REDACTED_AWS_KEY]", value)
    value = GITHUB_TOKEN_RE.sub("[REDACTED_GITHUB_TOKEN]", value)
    value = SLACK_TOKEN_RE.sub("[REDACTED_SLACK_TOKEN]", value)
    value = URL_CREDENTIAL_RE.sub(r"\1[REDACTED_USER]:[REDACTED_PASSWORD]@", value)
    value = SECRET_ASSIGNMENT_RE.sub(r"\1[REDACTED]", value)
    value = SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", value)
    value = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    return value


def redact_for_llm(error_trace: str) -> str:
    """Return an LLM-safe representation while preserving useful diagnostics."""
    if not settings.llm_redaction_enabled:
        return error_trace

    value = str(error_trace)
    if REQUEST_BODY_MARKER in value and settings.llm_redact_request_bodies:
        prefix, body = value.split(REQUEST_BODY_MARKER, 1)
        value = prefix + REQUEST_BODY_MARKER + _redact_request_body(body)
    return redact_text(value)


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
