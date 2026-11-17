#!/usr/bin/env bash
# Démarrage de la démo tout-en-un : PostgreSQL local -> import du corpus démo -> API + interface (port 7860).
# Le stockage d'un Space gratuit est éphémère : la base est recréée à chaque démarrage.
set -euo pipefail

PGDATA="${PGDATA:-$HOME/pgdata}"
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" -U user -A trust >/dev/null
fi
pg_ctl -D "$PGDATA" -o "-p 5432 -k /tmp -c listen_addresses=localhost" -l "$HOME/postgres.log" -w start
createdb -h localhost -U user aerodocs 2>/dev/null || true

cd "$HOME/app"
python -m scripts.seed_demo "$HOME/demo"
exec uvicorn app.main:app --host 0.0.0.0 --port 7860
