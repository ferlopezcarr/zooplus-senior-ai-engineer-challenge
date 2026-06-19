.PHONY: install run test

install:
	uv sync --group test

run:
	uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests
