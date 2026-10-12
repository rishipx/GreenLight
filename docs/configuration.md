# Configuration

All settings are environment variables (optionally loaded from `.env`). See `.env.example` for a template.

## Core

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` makes the API refuse to start unless required secrets are set. |
| `DATABASE_URL` | `sqlite:///./greenlight.db` | SQLAlchemy URL. Use PostgreSQL (`postgresql+psycopg://…`) in production. |
| `POSTGRES_PASSWORD` | `greenlight` | Docker Compose only. Set before the volume is first created. |

## Required in production

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_IDS`, `TELEGRAM_WEBHOOK_SECRET`, `INGEST_API_KEY`, `READ_API_KEY`, `AGENT_WEBHOOK_SECRET`, `ALERTMANAGER_WEBHOOK_SECRET`, `GENERIC_WEBHOOK_SECRET`. Use a distinct value for each secret.

## LLM triage

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_API_KEY` | unset | Without a key, incidents are recorded with no recommendation. |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint. |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model name. |
| `LLM_REDACTION_ENABLED` | `true` | Redact secrets and personal data before sending text to the provider. |
| `LLM_REDACT_REQUEST_BODIES` | `true` | Redact structured request bodies; replace unstructured bodies entirely. |

## Remediation and approval

| Variable | Default | Description |
| --- | --- | --- |
| `REMEDIATION_MODE` | `dry-run` | `dry-run` or `execute`. |
| `REMEDIATION_TIMEOUT_SECONDS` | `15` | Per-runbook execution timeout. |
| `APPROVAL_TTL_SECONDS` | `300` | Approval token lifetime. |
| `N8N_WEBHOOK_URL` | unset | Optional completion notification target. |

## Request protection

| Variable | Default | Description |
| --- | --- | --- |
| `MAX_REQUEST_BYTES` | `65536` | Maximum request body size (checked against `Content-Length`). |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | `30` / `60` | Per-path, per-client limit. |
| `DEDUPE_WINDOW_SECONDS` | `300` | An identical alert (service, host, trace) while an incident is still `PENDING` returns the existing incident. `0` disables. |

## Worker

| Variable | Default | Description |
| --- | --- | --- |
| `WORKER_POLL_SECONDS` | `1.0` | Idle poll interval. |
| `WORKER_LEASE_SECONDS` | `60` | Must exceed `REMEDIATION_TIMEOUT_SECONDS`. |
| `WORKER_MAX_ATTEMPTS` | `3` | Attempts before a job is failed permanently. |

## Journal agent

Set in the agent environment (see `agents/journal/greenlight-journal.sh`): `GREENLIGHT_URL`, `GREENLIGHT_WEBHOOK_SECRET`, `GREENLIGHT_SERVICE_NAME`, `GREENLIGHT_JOURNAL_UNIT`, `GREENLIGHT_MATCH_REGEX`, `GREENLIGHT_COOLDOWN_SECONDS` (default `300`).
