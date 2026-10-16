# Operations

## Configurations

Local development uses SQLite, eager jobs, and `npm run dev` with a proxy to port 8000. Compose uses Postgres, Redis, Celery, and Nginx. Both default to demonstration mode.

## Migrations

`alembic upgrade head` creates the schema from the SQLAlchemy models. The API container retries the migration until Postgres accepts connections, then creates the development accounts and source settings if they are missing. It does not insert an investigation.

To migrate a copy of the database, take a backup first, run `alembic upgrade head`, and restart the API. Do not point a new migration at a database you have not backed up.

## Backup and restore

Postgres data lives in the `pgdata` volume.

```bash
docker compose exec db pg_dump -U piae piae > piae.sql
docker compose exec -T db psql -U piae piae < piae.sql
```

Neo4j can be rebuilt from Postgres by re-running an investigation or calling the projection after `NEO4J_URI` is set. Do not treat Neo4j as the only copy.

## Health and shutdown

`GET /api/health` checks the database and, when configured, Redis. Compose restarts the API and worker unless they are stopped. Stopping Compose with `docker compose stop` lets the worker finish its current task only until the stop timeout. In-process eager jobs stop with the API process.

## TLS

Terminate TLS at a proxy using `nginx/nginx.conf` as a starting point. The application container does not ship certificates.

## Troubleshooting

- Login fails after a password change in `.env` if the user row already exists. The seed does not reset passwords.
- An investigation stays queued when Compose is up but the worker is down. Check `docker compose logs worker`.
- An empty live investigation means the connectors were skipped or failed. The report limitations list names the provider. Demonstration mode will not call them.
- Graph projection warnings in the log mean Neo4j was configured but unreachable. The workspace still reads Postgres.
- If `crt.sh` or RDAP times out, the job still completes with the other sources and a limitation.
