#!/bin/sh
set -eu
attempt=0
until alembic upgrade head; do
  attempt=$((attempt + 1))
  if [ "$attempt" -gt 30 ]; then
    echo "database migrations did not complete" >&2
    exit 1
  fi
  sleep 2
done
python -m app.seed
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
