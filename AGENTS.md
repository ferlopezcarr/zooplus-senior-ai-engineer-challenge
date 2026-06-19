# Repository AGENTS

## Repository Context

- This repository is a PoC scaffold for a product-grounded assistant.
- Current deployable unit: `apps/api`.

## Quick Documentation Routing

| Need | Go to |
| --- | --- |
| Repository orientation or repo map | `README.md` |
| Repository topology, deployable boundaries, or documentation ownership | `docs/architecture/overview.md` |
| Repository-wide durable documentation rules | `docs/specs/repo-context-bootstrap.md` |
| API setup, run, test, or configuration | `apps/api/README.md` |
| API runtime structure, technologies, or package boundaries | `apps/api/docs/architecture/overview.md` |
| API-local routes, behavior, or durable runtime expectations | `apps/api/docs/specs/` |

## Documentation Ownership

| Area | Scope | Canonical location |
| --- | --- | --- |
| Root orientation | Repository entry point and navigation | `README.md` |
| Root agent guidance | Repo map, commands, and global conventions | `AGENTS.md` |
| Root architecture | Repository-level topology and ownership boundaries only | `docs/architecture/` |
| Root specs | Repository-wide durable rules only | `docs/specs/` |
| API execution | API-local setup, run, test, and configuration | `apps/api/README.md` |
| API architecture | API-local runtime structure, stack, routes, and boundaries | `apps/api/docs/architecture/` |
| API specs | API-local durable behavior and contracts | `apps/api/docs/specs/` |

## Root vs App-local Boundary

| Root docs own | `apps/api` docs own |
| --- | --- |
| Repository topology | API runtime structure |
| Deployable boundaries | API technologies and tooling |
| Documentation ownership rules | API routes and behavior |
| Repo-wide durable rules | API-local setup, run, test, and config |

## Deployable Units

| Path | Purpose | Current state |
| --- | --- | --- |
| `apps/api` | Current API deployable | Owns the runnable service and its local documentation. |

## Conventions

- Keep repository-facing docs concise, English-only, and current-state-only.
- Use Engram as the project-state and SDD control mechanism; do not use repository files for planning-state control.
- Treat `README.md` as the root index and `apps/api/README.md` as the local execution guide.
- Keep repository-wide structure in `docs/architecture/` and repository-wide rules in `docs/specs/`.
- Keep API-local structure, technologies, runtime details, and behavior under `apps/api/docs/`.
- Do not describe the API stack, FastAPI, Python tooling, pytest, routes, or hexagonal package boundaries as repository-wide architecture.
- Prefer explicit boundaries over hidden configuration.
- Keep Python artifacts under `apps/api`.

## Execution Notes

- Install dependencies with `cd apps/api && make install`.
- Run the service with `cd apps/api && make run`.
- Run focused regression checks with `cd apps/api && make test`.
