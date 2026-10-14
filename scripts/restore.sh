#!/bin/bash
#
# Restore a backup made by scripts/backup.sh (or `prod.py backup`):
#
#   scripts/restore.sh <db_backup_file> [media_backup_file]
#
# Overwrites the current database (and media, if given). Encrypted .gpg
# archives are decrypted with BACKUP_PASSPHRASE_FILE, or gpg asks for the
# passphrase. The implementation is `prod.py restore`; see backup.sh for why
# this wrapper exists.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${COMPOSE_FILE:-}" ] && [ -f "${REPO_DIR}/.env" ]; then
    COMPOSE_FILE=$(grep -E '^[[:space:]]*COMPOSE_FILE=' "${REPO_DIR}/.env" | tail -n 1 \
        | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//') || true
fi

# Arguments are paths relative to where the caller stands; resolve them
# before changing directory.
ARGS=()
for arg in "$@"; do
    if [ -e "$arg" ]; then ARGS+=("$(cd "$(dirname "$arg")" && pwd)/$(basename "$arg")"); else ARGS+=("$arg"); fi
done

cd "$REPO_DIR"
exec python3 "${REPO_DIR}/prod.py" restore --compose-file "${COMPOSE_FILE:-docker-compose.yml}" "${ARGS[@]}"
