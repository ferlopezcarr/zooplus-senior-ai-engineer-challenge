# Second Delivery Overview

This document records the second delivery delta for the `apps/api` PoC. It captures the latest runtime additions without rewriting the first delivery snapshot.

## Delivery Delta

- `POST /chat` keeps dataset-grounded retrieval as the first step.
- Final answer synthesis can now use an optional OpenAI-compatible provider.
- When LLM mode is inactive, or when provider calls fail at runtime, the API still returns deterministic catalog-grounded answers.

## Runtime Additions

### Activation policy

- `main.py` loads `apps/api/.env` through `python-dotenv` during `build_app()` startup.
- LLM mode is enabled only when both `LLM_BASE_URL` and `LLM_API_KEY` are non-blank after environment and `.env` loading.
- `LLM_BASE_URL` must be an HTTPS base URL and is converted to the narrow `/chat/completions` contract used by the provider client.
- `LLM_TIMEOUT_SECONDS` is optional and configures provider request timeout; the default remains `10.0` seconds.

### Fallback and failure behavior

- Missing or blank LLM configuration does not block startup; the app stays in deterministic mode.
- A present but invalid `LLM_BASE_URL` fails fast at startup, even if `LLM_API_KEY` is missing.
- Provider HTTP failures, empty answers, or malformed provider output do not surface as user-facing LLM errors; the runtime falls back to deterministic grounded answers.
- Provider diagnostics are sanitized before logging so API keys and bearer tokens are redacted.

## Runtime Shape

`HTTP request -> FastAPI route -> application use case -> dataset-backed retrieval -> response context -> optional LLM or deterministic answer generation -> JSON response`

## Startup and Verification

- Local startup now uses factory mode: `uvicorn main:build_app --factory`.
- Manual local LLM e2e coverage exists via `make test-e2e`.
- The default runtime and standard non-e2e test flow still work without LLM credentials.

## Package Boundary Notes

- `src/application` now owns response-context assembly and answer-generation strategy selection.
- `src/infrastructure/output` now covers both dataset retrieval and the optional OpenAI-compatible answer client.
- HTTP DTOs and domain models remain separated across transport and domain boundaries.

## Deferred Work

- Embeddings, vector search, reranking, and broader retrieval-quality improvements remain out of scope.
- LLM evaluation depth is still limited to focused regression and manual local e2e checks.
- A stricter port abstraction around the external LLM provider can be introduced later if provider surface area grows.
