.PHONY: install lint format test check test-postgres run worker up down simulate

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

test:
	pytest -q

check: lint test

# Requires a running PostgreSQL; see the Development section of README.md.
test-postgres:
	pytest -q tests/integration/postgres

run:
	uvicorn greenlight.main:app --reload

worker:
	python -m greenlight.worker

up:
	docker compose up --build

down:
	docker compose --profile n8n down

simulate:
	./scripts/simulate_incident.sh
