# API Architecture Overview

## Deployable Summary

`apps/api` is the current API deployable. It owns the Python runtime, HTTP entrypoint, local tests, and API-local architecture and spec documents.

## Stack

| Area | Current choice |
| --- | --- |
| Web framework | FastAPI |
| Language | Python 3.14 |
| Dependency and command runner | `uv` |
| Test runner | `pytest` |

## Runtime Shape

- `main.py` builds the FastAPI application and exports `app`.
- The current route surface exposes service metadata, health, and grounded chat.
- `src/` reserves hexagonal package boundaries for domain, application, and infrastructure code.

## Package Boundaries

| Path | Role |
| --- | --- |
| `main.py` | FastAPI bootstrap and route registration. |
| `src/domain` | Domain boundary for core business concepts and rules, with domain models, value objects, and shared normalization service split by concern. |
| `src/application` | Application boundary for use-case orchestration. |
| `src/infrastructure` | Infrastructure boundary for adapters and framework-facing code. |
| `src/infrastructure/input` | Input adapter boundary. |
| `src/infrastructure/input/http/chat` | HTTP chat adapter boundary for route wiring and transport/domain mapping. |
| `src/infrastructure/input/http/chat/model` | HTTP DTO boundary for request, response, and nested transport models. |
| `src/infrastructure/output` | Output adapter boundary for dataset-backed retrieval. |
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
| `POST /chat` | Implemented | Validates `site_id` and `query`, attempts retrieval first, and returns a grounded JSON response or dataset-readiness failure. |

## Request Flow

`HTTP request -> FastAPI route -> chat mapper -> chat use case -> chat mapper -> JSON response`

## Deployable Boundary

- This document describes only `apps/api`.
- API-specific framework, testing, and package-structure choices do not define repository-wide architecture.
- This document does not define architecture outside `apps/api`.

## Documentation Pointers

- Use `../../../../README.md` for repository-level orientation.
- Use `../specs/assistant-api-runtime.md` for the current HTTP contract.
- Use `../specs/dataset-grounded-retrieval.md` for the current retrieval boundary.
