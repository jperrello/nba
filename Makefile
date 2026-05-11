.PHONY: install test lint typecheck cli db-up db-down db-reset

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

typecheck:
	pyright .

cli:
	python -m nba

db-up:
	docker compose up -d --wait
	docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $${NBA_DB_USER:-nba} -d $${NBA_DB_NAME:-nba} -f /migrations/0001_init.sql

db-down:
	docker compose down

db-reset:
	docker compose down -v
	$(MAKE) db-up
