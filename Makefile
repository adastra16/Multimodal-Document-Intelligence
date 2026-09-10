.PHONY: install-dev test lint typecheck

install-dev:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check backend

typecheck:
	mypy
