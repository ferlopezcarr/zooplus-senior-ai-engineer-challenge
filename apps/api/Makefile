.PHONY: install run test lint format

install:
	uv sync --group test --group lint

run:
	uv run uvicorn main:build_app --factory --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests

lint:
	uv run --group lint ruff check .

format:
	uv run --group lint ruff format .
