# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make lint
make test
```

PostgreSQL locking tests need a database:

```bash
TEST_POSTGRES_URL=postgresql+psycopg://greenlight:greenlight@localhost:5432/greenlight_test make test-postgres
```

## Project rules

- Preserve the core invariant: the LLM may only return a key from `RUNBOOKS`; execution happens only in the worker after human approval.
- Any change touching authentication, approval, runbooks or redaction requires a test.
- Never commit secrets. `.env` is git-ignored; add new settings to `.env.example` and `docs/configuration.md`.
- New runbooks must be idempotent and non-interactive.
- CI must pass: `ruff check`, `ruff format --check`, shellcheck, the SQLite and PostgreSQL test suites, and the `database/schema.sql` apply check.

## Pull requests

Keep them small and focused. Describe the behavior change and any threat-model impact.

By contributing, you agree your contributions are licensed under the MIT License.
