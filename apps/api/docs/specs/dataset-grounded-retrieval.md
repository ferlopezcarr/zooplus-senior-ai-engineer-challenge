# Dataset-Grounded Retrieval

## Purpose

Record the current retrieval boundary for `apps/api`.

## Current State

- No dataset retrieval flow is wired into the running API.
- No response generation from `product_catalog_dataset.json` is exposed at runtime.
- API-local docs must not describe grounded retrieval as implemented behavior.

## Durable Boundary

- Retrieval work for this repository remains constrained to dataset-backed, site-scoped behavior.
