.PHONY: install test lint typecheck cli

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
