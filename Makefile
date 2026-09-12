.PHONY: install-dev test coverage lint typecheck run

install-dev:
	python -m pip install -e ".[dev]"

test:
	pytest

coverage: test

lint:
	ruff check backend

typecheck:
	mypy

run:
	python -m uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
