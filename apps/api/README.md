# API

Local execution guide for the current `apps/api` service.

## Local Docs

- `docs/architecture/overview.md` for API runtime structure.
- `docs/specs/assistant-api-runtime.md` for the current HTTP contract.
- `docs/specs/dataset-grounded-retrieval.md` for the current retrieval boundary.

## Setup

```bash
make install
```

`make install` syncs the local runtime and test dependencies declared in `pyproject.toml`.

## Run

```bash
make run
```

The service starts on `http://127.0.0.1:8000` unless you change the Uvicorn command locally.

## Test

```bash
make test
```

## Current Routes

- GET `/` returns service status metadata.
- GET `/health` returns health status metadata.
- POST `/chat` is not implemented and returns `404`.

## Configuration

- No runtime environment variables are required for the current bootstrap service.
- Dependency management uses `uv` through the local `apps/api/Makefile`.

## Layout

- `main.py` contains FastAPI bootstrap wiring.
- `src/` keeps visible domain, application, and infrastructure boundaries.
- `tests/` contains focused regression checks for the current runtime endpoints.
