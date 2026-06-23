# API Scripts

## Product catalog feed

`product_catalog_feed.py` loads the static product catalog dataset into PostgreSQL for the runtime `/public/chat` retrieval path.

### Prerequisites

- Local PostgreSQL/pgvector is running.
- Alembic migration has been applied.

### Configure the database URL once

Prefer the local `.env` workflow so Alembic and the feed script use the same value every time.

1. Start PostgreSQL with the credentials from `infrastructure/local/.env`.
2. Copy `apps/api/.env.example` to `apps/api/.env` if you do not have it yet.
3. Set `PRODUCT_CATALOG_DATABASE_URL` in `apps/api/.env` so it matches your local PostgreSQL credentials.

Example local-only value:

```dotenv
PRODUCT_CATALOG_DATABASE_URL=postgresql+psycopg://<user>:<password>@example.test:5432/catalog
```

One-time setup from `apps/api`:

```bash
cp .env.example .env
```

If you prefer not to store it in `apps/api/.env`, export the same value in your shell before running Alembic or feed commands.

Run from `apps/api`:

```bash
uv run alembic upgrade head
uv run python scripts/product_catalog_feed.py --dry-run
uv run python scripts/product_catalog_feed.py
uv run python scripts/product_catalog_embedding_backfill.py --dry-run --limit 10
uv run python scripts/product_catalog_embedding_backfill.py --limit 50
```

- Alembic and the feed script both load `apps/api/.env` automatically.
- `--dry-run` validates and maps the dataset without opening a database connection.
- The feed collapses duplicate source rows by `article_id` before upsert, so the current dataset loads as 287 unique catalog entries instead of 300 raw rows.
- The upsert is safe to rerun and preserves existing non-null `embedding` values.
- `POST /public/chat` requires `PRODUCT_CATALOG_DATABASE_URL` and reads `product_catalog_entries` from PostgreSQL at API startup.
- `POST /public/chat` opportunistically uses pgvector matches with similarity `>= 0.3` and falls back to lexical matching when embeddings are missing, sparse, or unavailable.
- Product embedding generation is available through `POST /internal/products/{article_id}/embedding`.
- `product_catalog_embedding_backfill.py` is a manual maintenance script. By default it only processes rows where `embedding IS NULL`; pass `--force` to recalculate existing vectors too.
- The embedding backfill script loads `apps/api/.env` automatically. Every run, including `--dry-run`, requires `PRODUCT_CATALOG_DATABASE_URL` because the script still counts and loads target rows from PostgreSQL before branching. Real runs also require `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, and `EMBEDDING_MODEL`. `EMBEDDING_BASE_URL` must be the complete HTTPS embeddings endpoint URL.
- Use `--dry-run` to inspect the current missing backlog plus the selected batch without calling the provider. The dry-run output reports the current missing count unchanged and how many rows would still remain only if the selected batch completed successfully. Use `--limit` to keep local batches small while still seeing the likely backlog after that batch.
- Every backfill run writes a trace file next to the script: `apps/api/scripts/product_catalog_embedding_YYYYMMDD-HHMMSS.log`. The log includes per-product `article_id`, status, model, short source/embedding hashes, embedding dimensions when available, duration, and failure messages without writing raw source text or full vectors.
