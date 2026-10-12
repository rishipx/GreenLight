# Disclaimer

GreenLight is a reference implementation. It is provided under the [MIT License](LICENSE), **without warranty of any kind**.

## Not production-ready as shipped

- Default `REMEDIATION_MODE=dry-run`. The bundled runbooks in `src/greenlight/services/runbooks.py` only `echo`; they perform no real remediation.
- Setting `REMEDIATION_MODE=execute` runs whatever commands are in `RUNBOOKS` on the worker host. You are solely responsible for reviewing, testing, and making those commands idempotent and safe.
- Jobs can run more than once (lease expiry → requeue). Runbooks must tolerate re-execution.
- No external secret management, versioned migrations (`create_all` at startup), distributed rate limiting, or HA/DR. See [docs/deployment.md](docs/deployment.md).
- Never mount a Docker socket, cloud credentials, or privileged access into the worker.

## AI-generated recommendations

- Triage output from an LLM can be wrong, incomplete, or manipulated by attacker-controlled log content (prompt injection).
- The design limits the model to selecting a key from a fixed allowlist; a human must approve every execution. Operators remain responsible for every approval.
- Do not use this project as the sole control for safety-, life-, or financial-critical systems.

## Data handling and privacy

- Incident traces are stored unredacted in the database. Redaction is applied only to the payload sent to the LLM provider.
- Redaction is heuristic and will miss some secrets and personal data. It is not a DLP product and does not provide regulatory compliance (GDPR, HIPAA, PCI-DSS, SOC 2, etc.).
- Content sent to a third-party LLM endpoint is subject to that provider's terms. Use a private or local endpoint for sensitive data.
- Telegram messages transit Telegram's servers.

## Security

- No independent security audit has been performed.
- The rate limiter is in-process and per-instance. `docker-compose.prod.yml` trusts `X-Forwarded-For` only from the Caddy container; any other proxy setup must configure `FORWARDED_ALLOW_IPS` or all clients share one bucket.
- Default credentials in `docker-compose.yml` (`greenlight/greenlight`) are for local development only. Change them for any shared environment.

## Third parties

Not affiliated with or endorsed by Telegram, Prometheus, Alertmanager, Grafana, Datadog, Sentry, AWS, Groq, OpenAI, n8n, or any other product named in this repository. Names are trademarks of their respective owners and are used for identification only.

## Liability

The authors and contributors accept no liability for outages, data loss, security incidents, or other damages resulting from use of this software. Use at your own risk.
