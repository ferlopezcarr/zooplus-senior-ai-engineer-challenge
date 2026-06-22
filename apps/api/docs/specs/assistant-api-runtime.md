# Assistant API Runtime

## Purpose

Record the current HTTP contract exposed by `apps/api`.

## Current Contract

- `GET /` returns service status metadata.
- `GET /health` returns process/liveness status only.
- `POST /chat` accepts `site_id` and `query` as JSON.
- Successful `POST /chat` responses return `answer` plus grounded `retrieved_products`.
- Each `retrieved_products` item is a slim evidence object: `article_id`, `product_id`, `variant_id`, `title`, `summary`, `category`, `site_id`, and `score`.
- Invalid `POST /chat` payloads return a validation error, including blank or overlong queries.
- Retrieval backend failures return `503` with a clear runtime error instead of an opaque `500`.
- `PRODUCT_CATALOG_DATABASE_URL` is required, and startup fails fast before serving requests when it is missing, blank, or the retrieval database is not ready.

## Documentation Rule

- API-local docs must describe the current runtime: PostgreSQL-backed lexical retrieval for `/chat`, required manual Alembic/feed preparation, and no startup migration/feed side effects.
