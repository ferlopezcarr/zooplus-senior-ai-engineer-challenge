# Assistant API Runtime

## Purpose

Record the current HTTP contract exposed by `apps/api`.

## Current Contract

- `GET /` returns service status metadata.
- `GET /health` returns process/liveness status only and remains the operational root health endpoint.
- `POST /public/chat` accepts `site_id` and `query` as JSON.
- Successful `POST /public/chat` responses return `answer` plus grounded `retrieved_products`.
- Each `retrieved_products` item is a slim evidence object: `article_id`, `product_id`, `variant_id`, `title`, `summary`, `category`, `site_id`, and `score`.
- `POST /internal/products/{article_id}/embedding` is a maintenance/admin-style route for one catalog product entry, where `{article_id}` identifies the catalog row to embed.
- Successful `POST /internal/products/{article_id}/embedding` responses stay small and return status metadata only, not the embedding vector.
- `POST /internal/products/{article_id}/embedding` skips recalculation when an embedding already exists unless `force=true` is provided.
- Public product-facing endpoints live under `/public/*`.
- Everything under `/internal/*` requires the `X-Internal-Token` header to match non-blank `INTERNAL_API_TOKEN`.
- Internal maintenance endpoints live under `/internal/*`.
- Missing `INTERNAL_API_TOKEN` makes internal routes unavailable with `503` without affecting public routes.
- Missing `X-Internal-Token` returns `401`; wrong `X-Internal-Token` returns `403`.
- `POST /internal/products/{article_id}/embedding` can still return `already_embedded` without embedding provider config when `force` is not requested and the row already has an embedding.
- Invalid `POST /public/chat` payloads return a validation error, including blank or overlong queries.
- Retrieval backend failures return `503` with a clear runtime error instead of an opaque `500`.
- `PRODUCT_CATALOG_DATABASE_URL` is required, and startup fails fast before serving requests when it is missing, blank, or the retrieval database is not ready.
- Embedding provider configuration is optional at startup; missing or invalid embedding config only makes `POST /internal/products/{article_id}/embedding` unavailable at request time.

## Documentation Rule

- API-local docs must describe the current runtime: PostgreSQL-backed lexical retrieval for `/public/chat`, required manual Alembic/feed preparation, and no startup migration/feed side effects.
