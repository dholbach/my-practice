# shellcheck shell=bash
# Sourced by backup.sh and restore.sh: sets COMPOSE_FILE to what a plain
# `docker compose` would use in this checkout. The environment wins, then
# COMPOSE_FILE in .env (last assignment, inline comment stripped), else the
# default docker-compose.yml. Needs REPO_DIR.

if [ -z "${COMPOSE_FILE:-}" ] && [ -f "${REPO_DIR}/.env" ]; then
    COMPOSE_FILE=$(grep -E '^[[:space:]]*COMPOSE_FILE=' "${REPO_DIR}/.env" | tail -n 1 \
        | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//') || true
fi
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
