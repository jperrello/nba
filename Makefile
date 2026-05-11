.PHONY: install test lint typecheck cli db-up db-down db-reset web web-serve web-dev

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
	@for m in $$(ls migrations/*.sql | sort); do \
		echo "applying $$m"; \
		docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $${NBA_DB_USER:-nba} -d $${NBA_DB_NAME:-nba} -f /$$m; \
	done

db-down:
	docker compose down

db-reset:
	docker compose down -v
	$(MAKE) db-up

web:
	cd web && npm install --no-fund --no-audit && npm run build

web-serve: web
	python3 scripts/web/serve.py

web-dev:
	@echo "vite :5173  |  gateway :8765  (ctrl-c stops both)"
	@trap 'kill 0' EXIT INT TERM; \
		python3 scripts/web/serve.py & \
		(cd web && npm run dev) & \
		wait
