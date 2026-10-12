# GreenLight

AI-assisted incident triage with human approval and isolated, allowlisted remediation.

> **AI can recommend a remediation, but it cannot execute one.**

GreenLight receives incidents from Linux/systemd, Prometheus Alertmanager or a generic observability webhook, triages them with an LLM, asks an operator for approval in Telegram, and then runs only a pre-approved runbook in a restricted worker. Every decision is recorded in an audit trail.

```text
Sources ──► FastAPI control plane ──► LLM triage ──► PostgreSQL ──► Telegram approval
                                                                          │
                                       audit trail ◄── allowlisted runbook ◄── durable job ◄── approve
```

## Features

- **Human-in-the-loop by design**: the model only returns a runbook key; execution requires a single-use, expiring operator approval.
- **Fail closed**: no LLM, invalid output or an unknown key means no recommendation and nothing to approve.
- **Durable worker**: PostgreSQL row-locking job queue with leases, retries and stale-job recovery.
- **Three input sources**: journald agent, Alertmanager, generic webhook, each with its own secret.
- **Privacy filter** for data sent to the LLM provider, plus incident de-duplication to limit alert floods.
- **Hardened containers**: non-root, read-only filesystem, dropped capabilities, internal-only database network.

## Quick start

```bash
cp .env.example .env
docker compose up --build        # PostgreSQL + API + worker; API on http://127.0.0.1:8000
./scripts/simulate_incident.sh   # send a sample incident
```

Without Docker (SQLite, no setup):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn greenlight.main:app --reload     # API docs: http://127.0.0.1:8000/docs
python -m greenlight.worker              # in a second terminal
```

In development, API endpoints stay open while their keys are unset. With `APP_ENV=production` the API refuses to start until every required secret is configured.

## Repository layout

```text
src/greenlight/
├── main.py            application factory and ASGI entry point
├── schemas.py         request, response and triage schemas
├── core/              config, logging, security, privacy filter
├── db/                engine/session and ORM models
├── services/          triage, runbooks, ingestion, incidents, Telegram client
├── api/               middleware and routes (health, incidents, webhooks, Telegram)
└── worker/            job queue, runbook loop, n8n notifier
agents/journal/        systemd journal watcher
deploy/                systemd unit and Caddy reverse-proxy config
database/schema.sql    PostgreSQL schema
examples/              Alertmanager receiver example
scripts/               helper scripts
docs/                  architecture, configuration, integrations, deployment, privacy
tests/                 unit/ and integration/ suites
```

## Documentation

| Topic | Document |
| --- | --- |
| Components, state machine, AI boundary | [docs/architecture.md](docs/architecture.md) |
| Every environment variable | [docs/configuration.md](docs/configuration.md) |
| Agent, Alertmanager, generic webhook, Telegram | [docs/integrations.md](docs/integrations.md) |
| Docker Compose, TLS, production checklist | [docs/deployment.md](docs/deployment.md) |
| Redaction and data handling | [docs/privacy.md](docs/privacy.md) |
| Limitations and responsibilities | [DISCLAIMER.md](DISCLAIMER.md) |
| Reporting vulnerabilities | [SECURITY.md](SECURITY.md) |
| Development workflow | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Development

```bash
make install     # editable install with dev tools
make lint        # ruff check + format check
make test        # unit + SQLite integration tests
```

PostgreSQL locking tests run when `TEST_POSTGRES_URL` is set; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Important

`REMEDIATION_MODE=dry-run` is the default and the bundled runbooks only `echo`. Read [DISCLAIMER.md](DISCLAIMER.md) before enabling `execute` mode or sending real incident data to an LLM provider.

## License

[MIT](LICENSE)
