# Submission Summary

This document is the assignment-facing submission artifact for the Zooplus Assistant PoC. It is intentionally self-contained: it summarizes the repository shape, the implemented solution, how to run it, the main trade-offs, and the next sensible steps.

## Repository Context

- The repository uses a monorepo-style layout, but `apps/api` is the only current deployable unit.
- The project is a product-grounded assistant PoC centered on a public chat API backed by a product catalog.
- Root docs own repository-level orientation only; service-specific runtime behavior and setup live under `apps/api`.

### Minimal repo map for reviewers

| Path | Why it matters for evaluation |
| --- | --- |
| `SUBMISSION.md` | Assignment-facing summary of the delivered solution |
| `apps/api` | Current runnable service |
| `apps/api/README.md` | Setup, run, test, and local execution details |
| `apps/api/docs/architecture/overview.md` | Runtime structure, routes, and package boundaries |
| `apps/api/docs/specs/` | Durable API and retrieval behavior |
| `infrastructure/local/` | Local PostgreSQL/pgvector bootstrap |

## High-Level Design

The current deliverable is a single FastAPI service under `apps/api`.

### Architectural style

The API follows a **hexagonal (ports-and-adapters)** structure organized as **vertical feature slices**. Business orchestration lives in feature application layers, domain rules stay close to each feature, and infrastructure adapters isolate HTTP transport, persistence, and external provider I/O.

At the moment, the codebase is organized mainly around two feature slices:

- **`chat`**: owns the public chat use case, retrieval orchestration, answer generation flow, and chat-facing models.
- **`product`**: owns product-catalog infrastructure concerns, including catalog reads, embedding generation, and embedding persistence.

A small **`core`** area is reserved only for truly shared utilities, instead of becoming a dumping ground for feature-owned models.

This structure keeps business flow readable, limits cross-feature coupling, and makes infrastructure decisions easier to replace without rewriting the use cases themselves.

- `POST /public/chat` is the public assignment-facing route.
- The route validates `site_id` and `query`, retrieves catalog evidence from PostgreSQL, and returns a grounded JSON response.
- Runtime code is split into:
  - `src/features/chat` for the chat vertical slice
  - `src/features/product` for product-catalog and embedding-related flows
  - `src/core` for genuinely shared logic such as text normalization
- The static JSON dataset is a feed input only; runtime retrieval reads from PostgreSQL.

### Retrieval behavior

The retrieval path is intentionally hybrid:

1. If embedding configuration is valid, `/public/chat` attempts pgvector retrieval first.
2. Vector matches are accepted only when similarity is `>= 0.3`.
3. Lexical retrieval then tops up missing results, or becomes the full fallback when vector retrieval is unavailable.
4. Responses stay site-scoped and grounded in retrieved catalog products.

This means the system gets better relevance when embeddings are available, without making embedding generation a hard startup dependency for the public chat route.

## Setup and Execution

Prerequisites: Python `>=3.14,<3.15`, `uv`, `docker compose`, and `make` available locally.

Minimum local validation flow for an evaluator:

1. Use Python `>=3.14,<3.15`.
2. Start local PostgreSQL/pgvector from `infrastructure/local`:

   ```bash
   cd infrastructure/local
   cp .env.example .env
   docker compose up -d
   docker compose ps
   ```

3. In `apps/api`, prepare the service:

   ```bash
   cd apps/api
   uv venv .venv
   source .venv/bin/activate
   make install
   cp .env.example .env
   ```

4. Edit `apps/api/.env` and set `PRODUCT_CATALOG_DATABASE_URL` (for example: `postgresql+psycopg://local_user:local_password@127.0.0.1:5432/local_db`).
5. Still in `apps/api`, prepare data and run the API:

   ```bash
   uv run alembic upgrade head
   uv run python scripts/product_catalog_feed.py
   make run
   ```

6. The API starts on `http://127.0.0.1:8000`.

For deeper operational detail, see [`apps/api/README.md`](apps/api/README.md).

Minimal manual check:

```bash
curl -X POST http://127.0.0.1:8000/public/chat \
  -H 'Content-Type: application/json' \
  -d '{"site_id": 1, "query": "dog food"}'
```

Regression checks:

- `cd apps/api && make test`
- `cd apps/api && make lint`
- `cd apps/api && make test-e2e` for the documented runtime-oriented checks

## Decisions and Trade-offs

### 1. `/public/chat` as the public contract

**Decision:** The public assistant endpoint lives at `POST /public/chat`.

**Why:** It keeps the assignment-facing surface explicit and leaves room for internal-only maintenance routes under `/internal/*`.

**Trade-off:** This is clear and production-friendly, but it does mean the service surface is slightly more structured than a single flat demo endpoint.

### 2. PostgreSQL runtime retrieval instead of reading JSON at request time

**Decision:** The dataset is loaded into PostgreSQL and served from there at runtime.

**Why:** It creates a cleaner production-shaped boundary: feed once, query many times, and keep retrieval logic close to the storage layer.

**Trade-off:** Local setup is heavier because migrations and feed loading are manual prerequisites.

**Additional PoC scope note:** The current manual ingestion/backfill path is intentionally script-based (`alembic`, `scripts/product_catalog_feed.py`, and `scripts/product_catalog_embedding_backfill.py`) and does not have the same level of automated coverage as the request-facing application flow. That is a conscious scope/budget choice for this PoC: it keeps the delivered system smaller and easier to review. A more robust long-term shape would be a dedicated ingestion/recalculation service with stronger operational and test guarantees, but building that service was intentionally left out of the current submission scope.

### 3. pgvector first, lexical fallback always available

**Decision:** Retrieval uses pgvector opportunistically and lexical matching as top-up/fallback.

**Why:** This improves relevance when embeddings are available while preserving graceful degradation when embedding configuration is missing, incomplete, invalid, or temporarily failing.

**Trade-off:** The retrieval path is more complex than pure lexical search, and ranking behavior is a blend of vector and lexical heuristics rather than a single scoring model.

### 4. Synchronous `/public/chat` path inside FastAPI

**Decision:** The service uses FastAPI, but the current `POST /public/chat` path remains synchronous end-to-end.

**Why:** For this PoC, sync SQLAlchemy engine usage and standard-library HTTP clients keep the implementation smaller, easier to reason about, and easy to run locally without adding async database/client complexity everywhere.

**Trade-off:** This is an explicit design choice for a pragmatic PoC, not the best long-term concurrency model. Under higher traffic, fully async database/provider integration or background execution boundaries would be a better fit. The current hexagonal structure keeps the blocking database and vendor integrations behind infrastructure adapters, which contains the impact of a future change.

### 5. Deterministic fallback instead of mandatory LLM dependency

**Decision:** The chat flow can answer deterministically from retrieved catalog products when LLM configuration is absent or provider calls fail.

**Why:** It keeps the core assignment behavior available by default and avoids turning third-party model access into a blocker for local execution.

**Trade-off:** Deterministic responses are less expressive than provider-backed answers, but they are safer and more reproducible for a local coding-task submission.

**Additional PoC scope note:** LLM-provider HTTP failures already get an initial sanitization and truncation pass before they are logged. That pass reduces obvious leakage risk, but it is not an exhaustive sanitizer for arbitrary third-party payloads. Other provider-facing paths avoid surfacing provider bodies by collapsing failures to generic API errors. More exhaustive provider-error normalization would be a sensible follow-up outside the current PoC scope.

## Future Roadmap

1. Move sync database/provider integrations to explicit async or worker-backed boundaries for better concurrency behavior.
2. Improve retrieval quality with stronger ranking, richer evaluation data, and clearer observability around vector-vs-lexical outcomes.
3. Add ingestion/backfill automation so local and deployment setup require fewer manual steps.
4. Add production-oriented auth, rate limiting, and structured monitoring around the public chat route.
5. Expand answer quality and grounding verification with dataset-focused evaluation suites.
