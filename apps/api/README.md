# API

Local execution guide for the current `apps/api` service.

## Local Docs

- `docs/architecture/overview.md` for API runtime structure.
- `docs/specs/assistant-api-runtime.md` for the current HTTP contract.
- `docs/specs/dataset-grounded-retrieval.md` for the current retrieval boundary.
- `../../infrastructure/local/README.md` for local PostgreSQL/pgvector startup.
- `scripts/README.md` for the static product catalog feed.
- `requests/*.http` for minimal local request examples.

## Local startup from zero

From the repository root:

```bash
cd apps/api
uv venv .venv # Only needed once to create the local virtualenv.
source .venv/bin/activate
make install
make run
```

- Python `>=3.14,<3.15` is required by `pyproject.toml`.
- `make install` syncs runtime, test, and lint dependencies into the local uv-managed virtualenv.
- Before `make run`, manually run Alembic plus `scripts/product_catalog_feed.py` so PostgreSQL is migrated and seeded for `/chat`.
- `make run` starts the API on `http://127.0.0.1:8000`.

## Test

Run from `apps/api`:

```bash
make test
```

## Manual LLM check

1. Copy `apps/api/.env.example` to `apps/api/.env`.
2. Uncomment `LLM_BASE_URL` in `apps/api/.env`, then set `LLM_API_KEY` to a real key instead of the example placeholder. Keep `LLM_MODEL` only if you want to override the default. Set `LLM_TIMEOUT_SECONDS` only if 10 seconds is too low or too high for your provider.
3. Run `make run` from `apps/api`.
4. In another terminal, call:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"site_id": 1, "query": "dog food"}'
```

- If `LLM_BASE_URL` or `LLM_API_KEY` is missing, startup logs one warning and the API stays on deterministic catalog answers.
- If `LLM_BASE_URL` is present but invalid, startup fails fast with a configuration error.
- If both are present, the app keeps the current OpenAI-compatible LLM path.

## Manual LLM e2e tests

Run from `apps/api`:

```bash
make test-e2e
```

- The tests use `TestClient(build_app())`, so no external server is needed.
- They load the same local `.env` path as the app runtime and skip cleanly when `LLM_BASE_URL` or `LLM_API_KEY` is missing or blank.
- `make test`, CI, and the tracked pre-commit flow stay on the default suite because `e2e` tests are excluded there.

## Lint

```bash
make lint
```

## Current Routes

- GET `/` returns service status metadata.
- GET `/health` returns process/liveness status only.
- POST `/chat` accepts `site_id` and `query`, then returns `answer` and `retrieved_products`.
- `POST /chat` returns `503` with a clear retrieval-unavailable error when the catalog backend fails during request handling.
- `POST /chat` reads `product_catalog_entries` from PostgreSQL only.

## Configuration

- `PRODUCT_CATALOG_DATABASE_URL` is required at runtime and must point to a migrated, seeded PostgreSQL database before the API starts.
- If `PRODUCT_CATALOG_DATABASE_URL` is missing, blank, or points to an unavailable database/table, startup fails fast with a concise configuration error.
- The JSON dataset remains a static source for `scripts/product_catalog_feed.py`; it is not a runtime retrieval source.
- Retrieval is still lexical; embeddings/vector search remain deferred.
- `.env` uses `python-dotenv`; `build_app()` loads `apps/api/.env` at startup with environment variables still taking precedence over file values.
- Optional LLM answer generation is enabled only when both `LLM_BASE_URL` and `LLM_API_KEY` are non-blank after `.env` loading. If either one is missing, the app logs a one-time startup warning and uses `DeterministicAnswerGenerator`. If `LLM_BASE_URL` is present but invalid, startup fails fast. `LLM_MODEL` still defaults to `gpt-4o-mini`. `LLM_TIMEOUT_SECONDS` defaults to `10` when missing or blank, and must parse as a positive integer or float when LLM mode is enabled. `LLM_API_KEY=replace-me` is treated like any other configured key value.
- Dependency management uses `uv` through the local `apps/api/Makefile`.

## Layout

- `main.py` contains FastAPI wiring plus required PostgreSQL retrieval selection.
- `src/domain` defines chat request/result value objects.
- `src/domain/service/text_normalizer_service.py` owns shared query normalization.
- `src/application` contains the chat use case.
- `src/infrastructure/input/http` exposes the FastAPI `POST /chat` adapter.
- `src/infrastructure/output` contains retrieval adapters and row-to-domain mapping.
- `tests/` contains focused unit and integration coverage for the current runtime.
