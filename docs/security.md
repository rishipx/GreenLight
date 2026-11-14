# Security notes

GreenLight reads untrusted log text, asks an LLM about it, and can end up running a command. These are the main risks, how each is handled, and the test that covers it.

| Risk | How it is handled | Test |
| --- | --- | --- |
| A log line tricks the model into proposing a dangerous command | The model can only return a key. Unknown keys are dropped. Commands live in code, not in model output | `tests/unit/services/test_triage.py`, `tests/unit/services/test_runbooks.py` |
| LLM is down or returns garbage | Incident is saved with no recommendation and no approve button | `tests/unit/services/test_triage.py`, `tests/integration/api/test_approval_flow.py` |
| Double click, or two operators approve at once | One conditional `UPDATE`; only one caller wins | `test_duplicate_approval_is_rejected`, `test_concurrent_approval_only_one_wins` |
| Wrong, expired or reused approval token | Single-use, expires in 300 s, stored only as a hash, compared in constant time | `test_wrong_token_is_rejected_and_changes_nothing`, `test_expired_token_is_rejected_and_changes_nothing` |
| Someone not allowed (or disabled) clicks Approve | Operators table; a disabled row wins over `TELEGRAM_ADMIN_IDS` | `test_unauthorized_callback`, `test_disabled_operator_stays_denied_even_if_listed_in_admin_ids` |
| Secrets in logs get sent to the LLM provider | Redaction filter runs on every outbound trace | `tests/unit/core/test_privacy.py` |
| Worker dies mid-job, or two workers grab one job | Lease, requeue and a retry limit; `FOR UPDATE SKIP LOCKED` | `tests/integration/worker/test_worker.py`, `tests/integration/postgres/test_job_locking.py` |

Smaller protections: webhook secrets are compared in constant time, requests are rate limited and size limited, identical open incidents are de-duplicated, and with `APP_ENV=production` the API refuses to start unless every secret is set. In Docker Compose the containers run as a non-root user with a read-only filesystem, and the worker has no outbound network access.

## Data sent to the LLM

Incident traces are stored unredacted in the database. Before a trace goes to the LLM provider, a filter removes common credential and personal-data patterns: auth and cookie headers, bearer tokens, API keys, passwords, JWTs, private keys, credentials in URLs, cloud tokens and email addresses. Unstructured request bodies are replaced with `[REDACTED_REQUEST_BODY]` unless `LLM_REDACT_REQUEST_BODIES=false`.

This is pattern matching, not a guarantee. It can miss secrets in unusual formats. For sensitive systems use a private or local LLM endpoint.

## Limitations

- The bundled runbooks only `echo`. With `REMEDIATION_MODE=execute` the worker runs whatever commands are in `RUNBOOKS`, so review them first and make them safe to repeat.
- The request size limit reads the `Content-Length` header, so a chunked upload is not capped by the app.
- The rate limiter is in memory, per instance.
- The schema is `schema.sql` plus `create_all`; there are no versioned migrations.
- No independent security review has been done.
- Not affiliated with Telegram, Prometheus, n8n or any other product named here.
