.PHONY: env up up-tracing down test lint fmt eval migrate api

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

migrate:  ## apply Alembic migrations to DATABASE_URL
	uv run alembic upgrade head

api:  ## run the API on 127.0.0.1:8000 (localhost only: there is no login)
	uv run uvicorn agency.api.app:create_app --factory --host 127.0.0.1 --port 8000
