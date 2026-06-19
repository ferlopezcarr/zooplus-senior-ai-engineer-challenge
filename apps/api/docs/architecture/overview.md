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
- The current route surface is a bootstrap shell.
- `src/` reserves hexagonal package boundaries for domain, application, and infrastructure code.

## Package Boundaries

| Path | Role |
| --- | --- |
| `main.py` | FastAPI bootstrap and route registration. |
| `src/domain` | Domain boundary for core business concepts and rules. |
| `src/application` | Application boundary for use-case orchestration. |
| `src/infrastructure` | Infrastructure boundary for adapters and framework-facing code. |
| `src/infrastructure/input` | Input adapter boundary. |
| `src/infrastructure/output` | Output adapter boundary. |
| `tests` | API-local regression coverage. |

## Current Route Surface

| Route | Status | Purpose |
| --- | --- | --- |
| `GET /` | Implemented | Returns service status metadata. |
| `GET /health` | Implemented | Returns health status metadata. |
| `POST /chat` | Not implemented | Returns `404` in the current bootstrap runtime. |

## Request Flow

`HTTP request -> FastAPI app in main.py -> route handler -> JSON response`

## Deployable Boundary

- This document describes only `apps/api`.
- API-specific framework, testing, and package-structure choices do not define repository-wide architecture.
- This document does not define architecture outside `apps/api`.

## Documentation Pointers

- Use `../../../../README.md` for repository-level orientation.
- Use `../specs/assistant-api-runtime.md` for the current HTTP contract.
- Use `../specs/dataset-grounded-retrieval.md` for the current retrieval boundary.
