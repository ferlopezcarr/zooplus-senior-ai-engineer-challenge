# Zooplus Assistant POC

Monorepo-style repository for a product-grounded assistant PoC. The current deployable unit is `apps/api`.

> Evaluators should start with [`SUBMISSION.md`](SUBMISSION.md).

## Documentation Ownership

| If you need... | Canonical location |
| --- | --- |
| Repository orientation, topology, deployable boundaries, or doc ownership | Root docs in this repository |
| Setup, run, test, configuration, runtime details, or API behavior | `apps/api` local docs |

## Project State

- Engram is the project-state and SDD control mechanism for this repository.
- Repository docs keep only durable current-state structure and runtime knowledge.

### Root docs

| Path | Owns |
| --- | --- |
| `README.md` | Repository entry point and navigation |
| `docs/architecture/overview.md` | Repository topology, deployable boundaries, and documentation ownership |
| `docs/specs/repo-context-bootstrap.md` | Repository-wide durable documentation rules |

### App-local docs (`apps/api`)

| Path | Owns |
| --- | --- |
| `apps/api/README.md` | API setup, run, test, and configuration |
| `apps/api/docs/architecture/overview.md` | API runtime structure, technologies, and package boundaries |
| `apps/api/docs/specs/` | API-local behavior, routes, and durable runtime expectations |

## Quick Start

1. Start local PostgreSQL/pgvector with [`infrastructure/local/README.md`](infrastructure/local/README.md).
2. Follow [`apps/api/README.md`](apps/api/README.md) for API env setup, catalog preparation, and local startup.
3. Use the API-local specs under `apps/api/docs/specs/` for the current runtime contract.

## Optional local Git pre-commit hook

From the repository root:

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

This installs the tracked pre-commit hook that runs the same `apps/api` checks as CI before each commit.

For API-local execution and runtime details, start with [`apps/api/README.md`](apps/api/README.md).
