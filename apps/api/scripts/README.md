# API Scripts

## Product catalog feed

`product_catalog_feed.py` loads the static product catalog dataset into PostgreSQL for the runtime `/chat` retrieval path.

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
PRODUCT_CATALOG_DATABASE_URL=postgresql+asyncpg://<user>:<password>@example.test:5432/catalog
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
```

- Alembic and the feed script both load `apps/api/.env` automatically.
- `--dry-run` validates and maps the dataset without opening a database connection.
- The feed collapses duplicate source rows by `article_id` before upsert, so the current dataset loads as 287 unique catalog entries instead of 300 raw rows.
- The upsert is safe to rerun and preserves existing non-null `embedding` values.
- `POST /chat` requires `PRODUCT_CATALOG_DATABASE_URL` and reads `product_catalog_entries` from PostgreSQL at API startup.
- The PostgreSQL path is still lexical/simple matching. Embeddings and vector similarity are intentionally deferred.
