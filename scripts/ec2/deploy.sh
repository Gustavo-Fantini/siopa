#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"

if ! command -v docker >/dev/null 2>&1; then
    echo "docker nao encontrado no servidor" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose plugin nao encontrado no servidor" >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "arquivo $ENV_FILE nao encontrado. Copie .env.production.example para .env e preencha as variaveis." >&2
    exit 1
fi

mkdir -p deploy
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/dev/null
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build --remove-orphans
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
