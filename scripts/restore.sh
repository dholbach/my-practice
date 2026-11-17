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

# shellcheck source=scripts/_compose_file.sh
. "${REPO_DIR}/scripts/_compose_file.sh"

# Arguments are paths relative to where the caller stands; resolve them
# before changing directory.
ARGS=()
for arg in "$@"; do
    if [ -e "$arg" ]; then ARGS+=("$(cd "$(dirname "$arg")" && pwd)/$(basename "$arg")"); else ARGS+=("$arg"); fi
done

cd "$REPO_DIR"
exec python3 "${REPO_DIR}/prod.py" restore --compose-file "$COMPOSE_FILE" "${ARGS[@]}"
