# Repository Architecture Overview

## Repository Topology

- The repository uses a monorepo-style layout.
- `apps/api` is the only current deployable unit.
- Root `docs/` holds repository-level durable context.

## Deployable Units

| Path | Role | Notes |
| --- | --- | --- |
| `apps/api` | API deployable | Owns the current runnable service and its local documentation. |

## Documentation Ownership

| Area | Scope | Canonical location |
| --- | --- | --- |
| Repository entry point | Human orientation | `README.md` |
| Agent navigation | Repository map, commands, conventions | `AGENTS.md` |
| Repository architecture | Topology, deployable boundaries, documentation ownership | `docs/architecture/` |
| Repository rules | Repository-wide durable rules | `docs/specs/` |
| API execution | API-local setup, run, test, configuration | `apps/api/README.md` |
| API architecture | API-local runtime structure and boundaries | `apps/api/docs/architecture/` |
| API behavior | API-local durable runtime behavior | `apps/api/docs/specs/` |

## Boundary Rule

Root architecture documents repository-level structure only. Deployable-specific implementation details belong to the local docs owned by that deployable.

## Local Architecture Pointer

For the current API architecture and route surface, use `apps/api/README.md` and `apps/api/docs/architecture/overview.md`.
