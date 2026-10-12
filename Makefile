.PHONY: install lint format test test-postgres run worker up down simulate

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

# Requires a running PostgreSQL; see CONTRIBUTING.md.
test-postgres:
	pytest -q tests/integration/test_postgres_locking.py

run:
	uvicorn greenlight.main:app --reload

worker:
	python -m greenlight.worker

up:
	docker compose up --build

down:
	docker compose down

simulate:
	./scripts/simulate_incident.sh
