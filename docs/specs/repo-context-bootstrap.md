# Repo Context Bootstrap

## Purpose

Define the minimum durable repository context required for humans, agents, and reviewers.

## Required Docs

- `README.md` must stay a short root index.
- `docs/architecture/overview.md` must describe repository topology, deployable units, and documentation ownership.
- `docs/specs/repo-context-bootstrap.md` must hold repository-level documentation rules only.
- `apps/api/README.md` must hold API-local setup, run, test, routes, and configuration details.
- `apps/api/docs/architecture/overview.md` must hold API-local runtime structure.
- `apps/api/docs/specs/` must hold API-local durable behavior summaries.

## Ownership Rules

- Root docs describe repository-wide context only.
- Local docs under `apps/api/` describe API-owned runtime details only.
- Durable docs describe the current repository state only.
- Engram holds project state and SDD control artifacts; repository docs remain the canonical home for durable current-state repository and runtime knowledge.

## Quality Rules

- Visible docs must stay concise, English-only, and non-duplicative.
- Visible docs must describe the current repository state rather than unpublished work.
