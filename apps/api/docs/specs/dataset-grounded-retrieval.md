# Dataset-Grounded Retrieval

## Purpose

Record the current retrieval boundary for `apps/api`.

## Current State

- The running API reads product data from PostgreSQL only.
- Retrieval stays scoped to the requested `site_id` before products are returned.
- Query matching stays lexical and uses normalized product text from product name, variant name, summary, description, pet type, and brand fields.
- Query normalization lives in `src/domain/service/text_normalizer_service.py`; row mapping stays under `src/infrastructure/output/service/`.
- `POST /public/chat` attempts retrieval before applying the off-topic fallback so valid catalog-only brand queries can succeed.
- Off-topic and no-result requests still return polite answers without invented products.
- `PRODUCT_CATALOG_DATABASE_URL` is required at startup and must be non-blank.
- Startup fails fast if the database connection or `product_catalog_entries` table is not ready.
- Startup does not run Alembic or `scripts/product_catalog_feed.py`; database preparation remains manual.
- `data/product_catalog_dataset.json` remains a static feed source for `scripts/product_catalog_feed.py`, not a runtime retrieval source.
- `POST /internal/products/{article_id}/embedding` can populate or refresh the stored vector for one catalog row, but `/public/chat` still does not query pgvector.

## Durable Boundary

- Retrieval work for this repository remains constrained to site-scoped lexical behavior; `/public/chat` vector similarity is still deferred.
