#!/bin/bash
#
# Back up the database and media of this checkout's stack.
#
# The implementation is `prod.py backup` — one copy shared with self-hosters
# who only have prod.py. This wrapper exists for the systemd unit and for
# checkout-based setups: it points prod.py at the compose file a plain
# `docker compose` would use here (COMPOSE_FILE from .env, else
# docker-compose.yml). Backups land in $MY_PRACTICE_DATA_DIR/backups; set
# BACKUP_PASSPHRASE_FILE in .env to encrypt them with gpg.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/_compose_file.sh
. "${REPO_DIR}/scripts/_compose_file.sh"

cd "$REPO_DIR"
exec python3 "${REPO_DIR}/prod.py" backup --compose-file "$COMPOSE_FILE" "$@"
