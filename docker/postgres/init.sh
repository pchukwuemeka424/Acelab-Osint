#!/bin/bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE USER piae_app WITH PASSWORD '${PIAE_APP_PASSWORD:-piae-app-dev}';
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO piae_app;
GRANT USAGE, CREATE ON SCHEMA public TO piae_app;
SQL
