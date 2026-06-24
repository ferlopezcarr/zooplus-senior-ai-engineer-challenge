# API

Local execution guide for the current `apps/api` service.

## Local Docs

- `docs/architecture/overview.md` for API runtime structure.
- `docs/specs/assistant-api-runtime.md` for the current HTTP contract.
- `docs/specs/dataset-grounded-retrieval.md` for the current retrieval boundary.
- `../../infrastructure/local/README.md` for local PostgreSQL/pgvector startup.
- `scripts/README.md` for the static product catalog feed.
- `requests/**/*.http` for minimal local request examples.

## Local startup

Python `>=3.14,<3.15` is required by `pyproject.toml`.

From `infrastructure/local`, start PostgreSQL/pgvector first:

```bash
cp .env.example .env
docker compose up -d
docker compose ps
```

Then from `apps/api`:

```bash
uv venv .venv # Only needed once.
source .venv/bin/activate
make install
cp .env.example .env
# edit .env before the next commands
uv run alembic upgrade head
uv run python scripts/product_catalog_feed.py
make run
```

- After `cp .env.example .env`, edit `apps/api/.env` and set `PRODUCT_CATALOG_DATABASE_URL` before running Alembic, the feed, or `make run`.
- `make run` starts the API on `http://127.0.0.1:8000`.
- The API does not run migrations or feed the catalog at startup.

## Test

Run from `apps/api`:

```bash
make test
```

## Manual request check

After `make run`, call:

```bash
curl -X POST http://127.0.0.1:8000/public/chat \
  -H 'Content-Type: application/json' \
  -d '{"site_id": 1, "query": "dog food"}'
```

- `requests/public/chat.http` includes a few cheap local request examples.

## Manual runtime e2e tests

Prerequisites:

1. Start local PostgreSQL from `../../infrastructure/local/README.md`.
2. Set `PRODUCT_CATALOG_DATABASE_URL` in `apps/api/.env`.
3. Prepare the runtime catalog from `apps/api`:

```bash
uv run alembic upgrade head
uv run python scripts/product_catalog_feed.py
```

4. Optional provider paths:
   - Set `LLM_BASE_URL` + `LLM_API_KEY` to verify provider-backed `/public/chat` answers.
   - Set `INTERNAL_API_TOKEN` + `EMBEDDING_BASE_URL` + `EMBEDDING_API_KEY` + `EMBEDDING_MODEL` to verify `POST /internal/products/{article_id}/embedding`.

Run from `apps/api`:

```bash
make test-e2e
```

- The tests use `TestClient(build_app())`, so no external server is needed.
- The LLM and embedding checks are optional and skip cleanly when their env vars are missing.

## Lint

```bash
make lint
```

## Canonical runtime docs

- Route behavior: `docs/specs/assistant-api-runtime.md`
- Retrieval behavior and guardrails: `docs/specs/dataset-grounded-retrieval.md`
- Runtime structure and package boundaries: `docs/architecture/overview.md`
- Feed and backfill commands: `scripts/README.md`
