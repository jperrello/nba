.PHONY: install test lint typecheck cli db-up db-down db-reset web web-serve web-dev install-daemon uninstall-daemon

LAUNCHD_DEST ?= $(HOME)/Library/LaunchAgents
LAUNCHCTL    ?= launchctl
PLIST_NAME   := com.nba.ingest.live.plist
PLIST_SRC    := infra/launchd/$(PLIST_NAME)
PLIST_DEST   := $(LAUNCHD_DEST)/$(PLIST_NAME)

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

install-daemon:
	@mkdir -p $(LAUNCHD_DEST) $(HOME)/.nba
	@sed "s|__HOME__|$(HOME)|g" $(PLIST_SRC) > $(PLIST_DEST)
	@$(LAUNCHCTL) unload $(PLIST_DEST) 2>/dev/null || true
	@$(LAUNCHCTL) load -w $(PLIST_DEST)
	@echo "installed: $(PLIST_DEST)"

uninstall-daemon:
	@$(LAUNCHCTL) unload -w $(PLIST_DEST) 2>/dev/null || true
	@rm -f $(PLIST_DEST)
	@echo "uninstalled: $(PLIST_DEST)"
