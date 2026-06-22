# Assistant API Runtime

## Purpose

Record the current HTTP contract exposed by `apps/api`.

## Current Contract

- `GET /` returns service status metadata.
- `GET /health` returns process/liveness status only.
- `POST /chat` accepts `site_id` and `query` as JSON.
- Successful `POST /chat` responses return `answer` plus dataset-backed `retrieved_products`.
- Each `retrieved_products` item is a slim evidence object: `article_id`, `product_id`, `variant_id`, `title`, `summary`, `category`, `site_id`, and `score`.
- Invalid `POST /chat` payloads return a validation error.
- Dataset-readiness failures return `503` with a clear runtime error instead of an opaque `500`.

## Documentation Rule

- API-local docs must describe only the dataset-backed chat behavior that the runtime currently exposes.
