# Dataset-Grounded Retrieval

## Purpose

Record the current retrieval boundary for `apps/api`.

## Current State

- The running API reads product data from PostgreSQL only.
- Retrieval stays scoped to the requested `site_id` before products are returned.
- Query matching always has a lexical fallback using normalized product text from product name, variant name, summary, description, pet type, and brand fields.
- Query normalization lives in `src/core/service/text_normalizer_service.py`; product-catalog row mapping and searchable-field knowledge live under `src/features/product/infrastructure/output/persistence/product_catalog_repository.py`.
- `POST /public/chat` attempts retrieval before applying the off-topic fallback so valid catalog-only brand queries can succeed.
- Off-topic and no-result requests still return polite answers without invented products.
- Off-topic requests must return `retrieved_products: []` even when lexical matching found catalog rows, unless the normalized query terms directly match the retrieved product search text (for example, valid brand-only catalog queries).
- `PRODUCT_CATALOG_DATABASE_URL` is required at startup and must be non-blank.
- Startup fails fast if the database connection or `product_catalog_entries` table is not ready.
- Startup does not run Alembic or `scripts/product_catalog_feed.py`; database preparation remains manual.
- `data/product_catalog_dataset.json` remains a static feed source for `scripts/product_catalog_feed.py`, not a runtime retrieval source.
- When the embedding provider config is complete and valid, `/public/chat` generates a query embedding and prefers site-scoped pgvector matches from `product_catalog_entries.embedding` only when similarity is `>= 0.3`.
- Lexical retrieval remains the fallback path for `/public/chat` when embeddings are missing/sparse or embedding generation fails.

## Durable Boundary

- Retrieval remains site-scoped. `/public/chat` now uses pgvector similarity opportunistically and falls back to lexical matching instead of making embeddings a startup dependency.
- Off-topic suppression is part of the `/public/chat` response contract: the API may reuse retrieval internally to classify a query, but it must not expose unrelated catalog evidence in `retrieved_products`.
