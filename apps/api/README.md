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
- Before `make run`, manually run Alembic plus `scripts/product_catalog_feed.py` so PostgreSQL is migrated and seeded for `/public/chat`.
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
curl -X POST http://127.0.0.1:8000/public/chat \
  -H 'Content-Type: application/json' \
  -d '{"site_id": 1, "query": "dog food"}'
```

- If `LLM_BASE_URL` or `LLM_API_KEY` is missing, startup logs one warning and the API stays on deterministic catalog answers.
- If `LLM_BASE_URL` is present but invalid, startup fails fast with a configuration error.
- If both are present, the app keeps the current OpenAI-compatible LLM path.

## Manual runtime e2e tests

Prerequisites:

1. Start local PostgreSQL from `infrastructure/local`:

```bash
cp .env.example .env
docker compose up -d
docker compose ps
```

2. Copy `apps/api/.env.example` to `apps/api/.env` if needed, then set `PRODUCT_CATALOG_DATABASE_URL` to your local PostgreSQL connection string.
3. Prepare the runtime catalog from `apps/api`:

```bash
uv run alembic upgrade head
uv run python scripts/product_catalog_feed.py
```

4. Optional provider paths:
    - Set `LLM_BASE_URL` + `LLM_API_KEY` to verify provider-backed `/public/chat` answers.
    - Set `INTERNAL_API_TOKEN` + `EMBEDDING_BASE_URL` + `EMBEDDING_API_KEY` + `EMBEDDING_MODEL` to verify `POST /internal/products/{article_id}/embedding`.
    - Set `EMBEDDING_BASE_URL` + `EMBEDDING_API_KEY` + `EMBEDDING_MODEL` before running the optional backfill command: `uv run python scripts/product_catalog_embedding_backfill.py --limit 50`.
    - `EMBEDDING_BASE_URL` must be the complete HTTPS embeddings endpoint URL.

Run from `apps/api`:

```bash
make test-e2e
```

- The tests use `TestClient(build_app())`, so no external server is needed.
- They cover `GET /health` plus the real PostgreSQL-backed `/public/chat` path.
- The LLM and embedding checks are optional and skip cleanly when their env vars are missing.
- If `PRODUCT_CATALOG_DATABASE_URL` is missing or the catalog DB is not ready, the suite skips with a message telling you to run Alembic and the feed first.
- `make test`, CI, and the tracked pre-commit flow stay on the default suite because `e2e` tests are excluded there.

## Lint

```bash
make lint
```

## Current Routes

- GET `/` returns service status metadata.
- GET `/health` returns process/liveness status only and remains the operational root health endpoint.
- POST `/public/chat` accepts `site_id` and `query`, then returns `answer` and `retrieved_products`.
- `POST /public/chat` returns `503` with a clear retrieval-unavailable error when the catalog backend fails during request handling.
- `POST /public/chat` reads `product_catalog_entries` from PostgreSQL only.
- Public product-facing endpoints live under `/public/*`.
- POST `/internal/products/{article_id}/embedding` is a local maintenance/admin-style endpoint that generates or refreshes one catalog product embedding on demand.
- In `POST /internal/products/{article_id}/embedding`, `{article_id}` identifies the catalog product entry row.
- Everything under `/internal/*` requires `X-Internal-Token` to match `INTERNAL_API_TOKEN`.
- Internal maintenance endpoints live under `/internal/*`.

## Configuration

- `PRODUCT_CATALOG_DATABASE_URL` is required at runtime and must point to a migrated, seeded PostgreSQL database before the API starts.
- If `PRODUCT_CATALOG_DATABASE_URL` is missing, blank, or points to an unavailable database/table, startup fails fast with a concise configuration error.
- The JSON dataset remains a static source for `scripts/product_catalog_feed.py`; it is not a runtime retrieval source.
- Retrieval is still lexical; `/public/chat` vector search remains deferred.
- `.env` uses `python-dotenv`; `build_app()` loads `apps/api/.env` at startup with environment variables still taking precedence over file values.
- Optional LLM answer generation is enabled only when both `LLM_BASE_URL` and `LLM_API_KEY` are non-blank after `.env` loading. If either one is missing, the app logs a one-time startup warning and uses `DeterministicAnswerGenerator`. If `LLM_BASE_URL` is present but invalid, startup fails fast. `LLM_MODEL` still defaults to `gpt-4o-mini`. `LLM_TIMEOUT_SECONDS` defaults to `10` when missing or blank, and must parse as a positive integer or float when LLM mode is enabled. `LLM_API_KEY=replace-me` is treated like any other configured key value.
- `INTERNAL_API_TOKEN` enables `/internal/*`. If it is missing or blank, internal endpoints return `503` while public routes still run.
- Internal routes return `401` when `X-Internal-Token` is missing and `403` when it is present but wrong.
- Optional embedding generation for `POST /internal/products/{article_id}/embedding` is enabled only when `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, and `EMBEDDING_MODEL` are non-blank. `EMBEDDING_BASE_URL` must be the complete HTTPS embeddings endpoint URL, with no params, query, or fragment. Missing or invalid embedding config does not block startup; that endpoint returns a safe unavailable error instead, except `already_embedded` responses still work without provider config when `force` is not requested. `EMBEDDING_TIMEOUT_SECONDS` defaults to `10` when missing or blank.
- `scripts/product_catalog_embedding_backfill.py` is the manual path for batch/backfill embeddings. It never runs at application startup. By default it only processes rows with missing embeddings; use `--force` to refresh existing vectors. Every run, including `--dry-run`, still needs `PRODUCT_CATALOG_DATABASE_URL` because the script counts and selects target rows before branching; real runs also need the embedding provider variables. Real runs report the actual remaining missing backlog after successful writes, while `--dry-run` keeps the current backlog unchanged and only estimates what would remain if the selected batch succeeded. Each run also writes a trace log next to the script as `scripts/product_catalog_embedding_YYYYMMDD-HHMMSS.log` with per-product status, hashes, dimensions, duration, and failure details.
- Dependency management uses `uv` through the local `apps/api/Makefile`.

## Layout

- `main.py` contains FastAPI wiring plus required PostgreSQL retrieval selection.
- `src/domain` defines chat request/result value objects.
- `src/domain/service/text_normalizer_service.py` owns shared query normalization.
- `src/application` contains the chat use case.
- `src/infrastructure/input/http` exposes the FastAPI `POST /public/chat` and `POST /internal/products/{article_id}/embedding` adapters, while `main.py` keeps root-level operational routes such as `GET /health`.
- `src/infrastructure/output` contains retrieval adapters, the embedding client/store, and row-to-domain mapping.
- `tests/` contains focused unit and integration coverage for the current runtime.
