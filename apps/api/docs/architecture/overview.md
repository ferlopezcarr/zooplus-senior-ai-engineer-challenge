# API Architecture Overview

## Deployable Summary

`apps/api` is the current API deployable. It owns the Python runtime, HTTP entrypoint, local tests, and API-local architecture and spec documents.

## Stack

| Area | Current choice |
| --- | --- |
| Web framework | FastAPI |
| Language | Python 3.14 |
| PostgreSQL retrieval and setup tooling | SQLAlchemy, Alembic, asyncpg, pgvector |
| Dependency and command runner | `uv` |
| Test runner | `pytest` |

## Runtime Shape

- `main.py` exposes `build_app()` and the runtime starts through `uvicorn main:build_app --factory`.
- The current route surface exposes service metadata, health, and grounded chat.
- `src/` reserves hexagonal package boundaries for domain, application, and infrastructure code.

## Package Boundaries

| Path | Role |
| --- | --- |
| `main.py` | FastAPI bootstrap, `.env` loading, configuration validation, and route registration. |
| `src/domain` | Domain boundary for core business concepts and rules, with domain models, value objects, and shared normalization service split by concern. |
| `src/application` | Application boundary for use-case orchestration, response context, and answer-generation strategies. |
| `src/infrastructure` | Infrastructure boundary for adapters and framework-facing code. |
| `src/infrastructure/input` | Input adapter boundary. |
| `src/infrastructure/input/http/chat` | HTTP chat adapter boundary for route wiring and transport/domain mapping. |
| `src/infrastructure/input/http/chat/model` | HTTP DTO boundary for request, response, and nested transport models. |
| `src/infrastructure/output` | Output adapter boundary for runtime retrieval, optional external answer generation, and related adapter helpers. |
| `src/infrastructure/output/llm_answer_client.py` | OpenAI-compatible HTTP client for optional answer synthesis from retrieved catalog context. |
| `src/infrastructure/output/service` | Output-adapter helpers for row-to-domain mapping. |
| `tests` | API-local regression coverage. |

## Model and DTO Conventions

- `src/domain/` contains domain models and value objects only, with one concept per file.
- `src/domain/service/` contains domain-owned normalization logic reused by query validation and retrieval.
- `src/infrastructure/input/http/chat/model/` contains FastAPI/Pydantic HTTP DTOs only.
- HTTP DTO names follow the transport-layer convention:
  - `...Request` for direct HTTP request body models.
  - `...Response` for direct HTTP endpoint response models.
  - `...DTO` for intermediate or nested reusable transport models.
- Domain models and HTTP DTOs are separate types even when names overlap. Route code may alias imports when a domain type such as `ChatRequest` coexists with an HTTP `ChatRequest`.

## Current Route Surface

| Route | Status | Purpose |
| --- | --- | --- |
| `GET /` | Implemented | Returns service status metadata. |
| `GET /health` | Implemented | Returns process/liveness status only. |
| `POST /chat` | Implemented | Validates `site_id` and `query`, retrieves grounded catalog evidence from PostgreSQL, and returns a grounded JSON response or retrieval-unavailable failure. |

## Request Flow

`HTTP request -> FastAPI route -> chat mapper -> chat use case -> PostgreSQL lexical retrieval -> response context -> optional LLM or deterministic answer generation -> chat mapper -> HTTP JSON response`

- `ChatUseCase` always retrieves catalog products first.
- Retrieved products are packaged into `ResponseContext` before answer generation.
- `LlmAnswerGenerator` is enabled only when `LLM_BASE_URL` and `LLM_API_KEY` are both non-blank after environment and `.env` loading.
- `LLM_TIMEOUT_SECONDS` optionally overrides provider timeout; otherwise the runtime uses the built-in default.
- If `LLM_BASE_URL` or `LLM_API_KEY` is missing or blank, the use case stays in deterministic catalog-grounded mode.
- If `LLM_BASE_URL` is present but invalid, startup fails fast even when `LLM_API_KEY` is missing.
- If the provider request fails, the use case returns the deterministic catalog-grounded answer instead.
- Provider HTTP error diagnostics are sanitized before logging so secrets are not echoed back.
- Manual local LLM e2e coverage exists via `make test-e2e`, but the default runtime and default test flow do not require LLM credentials.
- The repository keeps local Docker Compose PostgreSQL + pgvector infrastructure under `infrastructure/local/docker-compose.yml`.
- Manual persistence commands live under `apps/api` via Alembic and `python scripts/product_catalog_feed.py`; both commands load `apps/api/.env`, and the feed preserves existing embeddings on rerun.
- `build_app()` requires `PRODUCT_CATALOG_DATABASE_URL`, selects PostgreSQL lexical retrieval for `/chat`, and fails fast when the database readiness check fails.
- `build_app()` does not run Alembic or catalog feed commands at startup, the JSON dataset is feed-only, and embeddings/vector similarity remain deferred.

## Deployable Boundary

- This document describes only `apps/api`.
- API-specific framework, testing, and package-structure choices do not define repository-wide architecture.
- This document does not define architecture outside `apps/api`.

## Documentation Pointers

- Use `../../../../README.md` for repository-level orientation.
- Use `../specs/assistant-api-runtime.md` for the current HTTP contract.
- Use `../specs/dataset-grounded-retrieval.md` for the current retrieval boundary.
- Use `./first-delivery.md` for the historical first milestone snapshot.
- Use `./second-delivery.md` for the second delivery delta.
