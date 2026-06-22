# API

Local execution guide for the current `apps/api` service.

## Local Docs

- `docs/architecture/overview.md` for API runtime structure.
- `docs/specs/assistant-api-runtime.md` for the current HTTP contract.
- `docs/specs/dataset-grounded-retrieval.md` for the current retrieval boundary.
- `requests/*.http` for minimal local request examples.

## Local startup from zero

From the repository root:

```bash
cd apps/api
uv venv .venv
source .venv/bin/activate
make install
make run
```

- Python `>=3.14,<3.15` is required by `pyproject.toml`.
- `make install` syncs runtime, test, and lint dependencies into the local uv-managed virtualenv.
- `make run` starts the API on `http://127.0.0.1:8000`.

## Format

```bash
make format
```

## Current Routes

- GET `/` returns service status metadata.
- GET `/health` returns process/liveness status only.
- POST `/chat` accepts `site_id` and `query`, then returns `answer` and `retrieved_products`.
- `POST /chat` returns `503` with a clear dataset-readiness error when the catalog file is missing, unreadable, or malformed.

## Configuration

- `CATALOG_DATASET_PATH` optionally overrides the dataset path; the default points to `data/product_catalog_dataset.json` in the repository root.
- Optional LLM answer generation is enabled only when `LLM_API_KEY` is set. The app uses `DeterministicAnswerGenerator` by default and `LlmAnswerGenerator` when configured; `LLM_MODEL` defaults to `gpt-4o-mini`, `LLM_BASE_URL` defaults to `https://api.openai.com/v1`, and deterministic catalog answers remain the fallback on missing config or LLM call failure.
- Dependency management uses `uv` through the local `apps/api/Makefile`.

## Layout

- `main.py` contains FastAPI wiring and dataset-path configuration.
- `src/domain` defines chat request/result value objects.
- `src/domain/service/text_normalizer_service.py` owns shared query normalization.
- `src/application` contains the chat use case.
- `src/infrastructure/input/http` exposes the FastAPI `POST /chat` adapter.
- `src/infrastructure/output` contains dataset loading and row-to-domain mapping.
- `tests/` contains focused unit and integration coverage for the current runtime.
