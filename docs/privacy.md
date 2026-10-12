# Privacy and data handling

Incident traces are stored unredacted for operational auditability. A separate filter runs on the text sent to the configured LLM provider (`LLM_REDACTION_ENABLED=true` by default).

The filter removes common credential and personal-data patterns: authorization and cookie headers, bearer and basic credentials, API keys, passwords, tokens, JWTs, private-key material, credentials embedded in URLs, AWS/GitHub/Slack-style tokens and email addresses. For generic webhooks with a structured request `body`, sensitive JSON fields are redacted and other diagnostic fields kept. Unstructured request bodies are replaced with `[REDACTED_REQUEST_BODY]` by default.

This is heuristic data minimization, not a DLP system. It cannot guarantee detection of every secret or personal-data value. For sensitive environments prefer a private or local LLM endpoint, restrict database access, minimize upstream logging and define retention policies. Set `LLM_REDACT_REQUEST_BODIES=false` only when preserving unstructured bodies for triage justifies the weaker posture.

Telegram approval audits store callback metadata only; the approval token and raw callback update are never persisted. Logs never contain the Telegram bot token.
