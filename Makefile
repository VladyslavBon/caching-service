.DEFAULT_GOAL := help
.PHONY: help install test test-unit test-integration coverage lint format run migrate db db-clean up down

# Plain echo instead of grep/awk: on Windows make runs recipes through cmd.exe,
# where those tools do not exist. Keep this list in sync with the targets below, and
# avoid shell metacharacters such as parentheses or semicolons in the text, as sh
# treats them as syntax.
help: ## Show this help
	@echo install           Install dependencies into .venv
	@echo test              Run all tests
	@echo test-unit         Run unit tests only
	@echo test-integration  Run integration tests only
	@echo coverage          Run all tests and print a per-file coverage table
	@echo lint              Check style, formatting and types, changes nothing
	@echo format            Fix lint issues and format the code
	@echo db                Start only the Postgres container
	@echo migrate           Apply database migrations
	@echo db-clean          Delete all cached data, keeping the schema. Needs a running database
	@echo run               Run the service locally with auto-reload, starts Postgres in Docker
	@echo up                Run the service and its database in Docker Compose
	@echo down              Stop Docker Compose, the data volume is kept

install: ## Install dependencies into .venv
	uv sync

test: ## Run all tests
	uv run pytest

test-unit: ## Run unit tests only
	uv run pytest tests/unit

test-integration: ## Run integration tests only
	uv run pytest tests/integration

coverage: ## Run all tests and print a per-file coverage table
	uv run pytest --cov

lint: ## Check style, formatting and types (changes nothing)
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src tests

format: ## Fix lint issues and format the code
	uv run ruff check --fix .
	uv run ruff format .

db: ## Start only the Postgres container (for running the service locally)
	docker compose up -d --wait db

migrate: ## Apply database migrations
	uv run alembic upgrade head

db-clean: ## Delete all cached data, keeping the schema (database must be running)
	uv run python scripts/clean_db.py

run: db migrate ## Run the service locally with auto-reload (needs Docker for Postgres)
	uv run uvicorn caching_service.main:app --reload

up: ## Run the service and its database in Docker Compose
	docker compose up --build

down: ## Stop Docker Compose and remove its containers (data volume is kept)
	docker compose down
