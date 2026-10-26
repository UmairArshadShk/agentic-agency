.PHONY: env up up-tracing down test lint fmt eval migrate

env:  ## create .env from .env.example with generated dev secrets (no-op if it exists)
	@test -f .env || ./scripts/make_env.sh

up: env  ## start Postgres
	docker compose up -d --wait postgres

up-tracing: env  ## start Postgres plus self-hosted Langfuse
	docker compose --profile tracing up -d --wait

down:
	docker compose --profile tracing down

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

fmt:
	uv run ruff check --fix .
	uv run ruff format .

eval:
	uv run pytest -m eval -o addopts=""

migrate:  ## wired up in the DB task
	@echo "no migrations yet"
