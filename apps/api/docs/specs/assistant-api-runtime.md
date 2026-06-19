# Assistant API Runtime

## Purpose

Record the current HTTP contract exposed by `apps/api`.

## Current Contract

- `GET /` returns service status metadata.
- `GET /health` returns health status metadata.
- `POST /chat` is not implemented in the bootstrap runtime and returns `404`.

## Documentation Rule

- API-local docs must not claim that chat behavior is available until the runtime exposes it.
