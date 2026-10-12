# Architecture

## Components

| Component | Responsibility |
| --- | --- |
| **API** (`greenlight.main`) | Accepts incidents, authenticates sources and operators, performs triage, handles Telegram callbacks, creates remediation jobs. It never executes remediation commands. |
| **PostgreSQL** | Stores incidents, operators, remediation jobs, approval metadata and audit events. |
| **Telegram** | Delivers the approval prompt to every operator listed in `TELEGRAM_ADMIN_IDS`; the first valid click wins. |
| **Worker** (`greenlight.worker`) | Claims queued jobs with `FOR UPDATE SKIP LOCKED`, runs only keys from `RUNBOOKS`, enforces timeouts and recovers stale jobs. |

## Request flow

```text
source ─► validate ─► de-duplicate ─► LLM triage ─► persist ─► Telegram prompt
                                                                   │
                                              ┌── dismiss ─────────┤
                                              │                    └── approve ─► durable job ─► worker ─► result + audit
                                           DISMISSED
```

## Incident state machine

```text
PENDING ── dismiss ──► DISMISSED
   │
   └── approve ──► EXECUTING ──► EXECUTED
                           └────► FAILED
```

Approval is a single database transaction: the incident must still be `PENDING`, the approval token must be valid, unexpired and unused, the remediation key must still be allowlisted, and the job is created in the same transaction. A second approval cannot queue another job.

An incident whose token expires stays `PENDING` with no actions available; re-send the alert to create a fresh incident.

## AI boundary

```text
incident log + source severity
        │
        ▼
structured LLM output (root cause, severity, remediation key, confidence)
        │
        ▼
validate key against RUNBOOKS ──► human approval ──► deterministic worker ──► runbook
```

The model selects a key; commands are defined only in `src/greenlight/services/runbooks.py`. If the LLM is unconfigured, fails, returns invalid output or proposes an unknown key, the incident is recorded with no recommendation and confidence `0`, and Telegram shows no approval button.

## Worker reliability

A `RUNNING` job whose `claimed_at` is older than `WORKER_LEASE_SECONDS` is requeued until `WORKER_MAX_ATTEMPTS`, then failed permanently and audited. The lease must exceed `REMEDIATION_TIMEOUT_SECONDS`. Because a requeued job can run again, **runbooks must be idempotent**.

## Security boundaries

- Separate credentials for ingest (`INGEST_API_KEY`), read (`READ_API_KEY`) and each webhook source; Telegram callbacks use their own secret header.
- Operators are stored in PostgreSQL with `ADMIN` or `APPROVER` roles.
- Approval tokens are random, short-lived, single-use and stored only as SHA-256 hashes; audits keep callback metadata, not raw payloads.
- Request bodies are size-limited and a per-instance rate limiter applies. Use a shared gateway or Redis for multi-instance deployments.
- The worker runs as a non-root user with dropped capabilities, `no-new-privileges`, a read-only filesystem, resource limits and no published ports.
- PostgreSQL row-level security is enabled for deployments that expose the database through PostgREST or Supabase. Application and worker connections are trusted server-side roles.
