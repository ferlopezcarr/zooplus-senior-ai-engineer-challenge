# Dataset-Grounded Retrieval

## Purpose

Record the current retrieval boundary for `apps/api`.

## Current State

- The running API reads product data only from `data/product_catalog_dataset.json` unless `CATALOG_DATASET_PATH` overrides it.
- Retrieval stays scoped to the requested `site_id` before products are returned.
- Query matching uses normalized dataset text from product name, variant name, summary, description, pet type, and brand fields.
- Query normalization lives in `src/domain/service/text_normalizer_service.py`; dataset row mapping stays under `src/infrastructure/output/service/`.
- `POST /chat` attempts retrieval before applying the off-topic fallback so valid catalog-only brand queries can succeed.
- Off-topic and no-result requests still return polite answers without invented products.
- Missing, unreadable, or malformed datasets surface as explicit readiness failures instead of opaque `500` responses.

## Durable Boundary

- Retrieval work for this repository remains constrained to dataset-backed, site-scoped behavior.
