# Local Infrastructure

Local Docker Compose assets live in this directory.

## PostgreSQL + pgvector

1. Copy `.env.example` to `.env` in this directory.
2. Change `POSTGRES_USER` and `POSTGRES_PASSWORD` to your own local values.
3. Start the stack from `infrastructure/local`:

```bash
cp .env.example .env
docker compose up -d
docker compose ps
```

Stop it with:

```bash
docker compose down
```

- PostgreSQL is published on `127.0.0.1` only.
- Active credentials come from your local `.env` file in this directory; the Compose file does not bake in `postgres/postgres` defaults.
- Set the app-side `PRODUCT_CATALOG_DATABASE_URL` separately in `apps/api/.env` as documented in `apps/api/scripts/README.md`.
