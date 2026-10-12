#!/bin/bash
#
# Backup script for My Practice
# Creates timestamped backups of PostgreSQL database and media files
#
# Media and backups are stored OUTSIDE the git repository.
# Set MY_PRACTICE_DATA_DIR in .env or environment to control the location.
# Default: <parent of repo>/my-practice-data
#
# Every archive is written to a temporary file, verified, and only then renamed
# into place — so a failed run never leaves a file that looks like a backup, and
# never reaches the retention cleanup at the bottom (which would otherwise rotate
# real backups out in favour of broken ones).
#

# pipefail is load-bearing: without it `pg_dump | gzip` reports gzip's exit
# status, so a pg_dump that never ran still produced a "successful" 20-byte file.
set -euo pipefail

# Resolve paths relative to this script so the script works regardless of cwd
# (e.g. when called by systemd with an arbitrary working directory).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment variables from repo root .env
# (strip full-line comments, inline trailing comments, and blank lines first —
# an inline "KEY=value  # comment" line otherwise makes xargs hand a bare "#"
# to export, which bash rejects as an invalid identifier)
if [ -f "${REPO_DIR}/.env" ]; then
    # Word splitting here is the point: each KEY=value pair becomes its own export argument.
    # shellcheck disable=SC2046
    export $(grep -v '^\s*#' "${REPO_DIR}/.env" | sed -E 's/[[:space:]]+#.*$//' | grep -v '^\s*$' | xargs)
fi

# Set defaults if not in .env
POSTGRES_DB=${POSTGRES_DB:-my_practice}
POSTGRES_USER=${POSTGRES_USER:-my_practice}

# External data directory (must be outside the git repo)
MY_PRACTICE_DATA_DIR="${MY_PRACTICE_DATA_DIR:-$(dirname "$REPO_DIR")/my-practice-data}"
BACKUP_DIR="${MY_PRACTICE_DATA_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"
MEDIA_BACKUP_FILE="${BACKUP_DIR}/media_backup_${TIMESTAMP}.tar.gz"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

fail() {
    echo -e "${RED}❌ $1${NC}" >&2
    exit 1
}

# Use docker directly; fall back to flatpak-spawn only inside a Flatpak sandbox
# (e.g. a Flatpak'd editor's terminal), where docker isn't on PATH. Hardcoding
# flatpak-spawn made every run on a normal host — including the systemd timer —
# fail with "command not found".
if command -v docker >/dev/null 2>&1; then
    DOCKER=(docker)
elif [ -f /.flatpak-info ] && command -v flatpak-spawn >/dev/null 2>&1; then
    DOCKER=(flatpak-spawn --host docker)
else
    fail "docker not found on PATH"
fi

# Temp files live in BACKUP_DIR so the final mv is an atomic rename on the same
# filesystem; removed on any exit path.
TMP_FILES=()
cleanup() {
    if [ ${#TMP_FILES[@]} -gt 0 ]; then
        rm -f "${TMP_FILES[@]}"
    fi
}
trap cleanup EXIT

echo -e "${BLUE}📦 Starting backup at $(date)${NC}"
echo -e "${BLUE}   Data directory: ${MY_PRACTICE_DATA_DIR}${NC}"

# Ensure backup directory exists (creates MY_PRACTICE_DATA_DIR/backups if needed)
mkdir -p "${BACKUP_DIR}"

# docker compose must be called from the repo directory. It honours COMPOSE_FILE
# from .env, so a production checkout can point it at docker-compose.prod.yml.
cd "$REPO_DIR"

echo -e "${BLUE}🗄️  Backing up PostgreSQL database...${NC}"

DB_TMP=$(mktemp "${BACKUP_DIR}/.db_backup_${TIMESTAMP}.XXXXXX")
TMP_FILES+=("$DB_TMP")

"${DOCKER[@]}" compose exec -T postgres pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --no-owner \
    --clean \
    --if-exists \
    | gzip > "${DB_TMP}" \
    || fail "Database backup failed (pg_dump or docker compose exec exited non-zero)"

# pg_dump writes this trailer only after the whole dump succeeded, so its
# presence proves the archive is complete, not just non-empty.
gzip -t "${DB_TMP}" || fail "Database backup is not a valid gzip archive"
# (Captured first rather than piped into `grep -q`: grep exiting early would
# SIGPIPE the producer and, under pipefail, fail a perfectly good backup.)
DB_TRAILER=$(gunzip -c "${DB_TMP}" | tail -n 5)
grep -q "PostgreSQL database dump complete" <<< "${DB_TRAILER}" \
    || fail "Database backup is incomplete (pg_dump trailer missing)"

mv "${DB_TMP}" "${DB_BACKUP_FILE}"
DB_SIZE=$(du -h "${DB_BACKUP_FILE}" | cut -f1)
echo -e "${GREEN}✅ Database backup complete: ${DB_BACKUP_FILE} (${DB_SIZE})${NC}"

echo -e "${BLUE}📁 Backing up media files...${NC}"

# Count media files in the container. A failure here (e.g. the django container
# is down) aborts the run rather than being mistaken for "no media".
MEDIA_COUNT=$("${DOCKER[@]}" compose exec -T django find /app/media -type f | wc -l) \
    || fail "Could not list media files in the django container"

if [ "${MEDIA_COUNT}" -gt 0 ]; then
    MEDIA_TMP=$(mktemp "${BACKUP_DIR}/.media_backup_${TIMESTAMP}.XXXXXX")
    TMP_FILES+=("$MEDIA_TMP")

    "${DOCKER[@]}" compose exec -T django tar czf - -C /app media > "${MEDIA_TMP}" \
        || fail "Media backup failed"

    ARCHIVED_COUNT=$(tar tzf "${MEDIA_TMP}" | grep -cv '/$') \
        || fail "Media backup is not a readable tar.gz archive"
    [ "${ARCHIVED_COUNT}" -eq "${MEDIA_COUNT}" ] \
        || fail "Media backup holds ${ARCHIVED_COUNT} files, expected ${MEDIA_COUNT}"

    mv "${MEDIA_TMP}" "${MEDIA_BACKUP_FILE}"
    MEDIA_SIZE=$(du -h "${MEDIA_BACKUP_FILE}" | cut -f1)
    echo -e "${GREEN}✅ Media backup complete: ${MEDIA_BACKUP_FILE} (${MEDIA_SIZE}, ${MEDIA_COUNT} files)${NC}"
else
    echo -e "${BLUE}ℹ️  No media files to backup${NC}"
    # Create empty marker file
    echo "No media files at $(date)" > "${MEDIA_BACKUP_FILE}.empty"
fi

# Only reached after every archive above was verified (set -e / fail exit
# earlier otherwise), so a run of failed backups can never rotate out the last
# good ones.
# Cleanup old backups (keep last 30 days)
echo -e "${BLUE}🧹 Cleaning up old backups (keeping last 30 days)...${NC}"
find "${BACKUP_DIR}" -name "db_backup_*.sql.gz" -mtime +30 -delete
find "${BACKUP_DIR}" -name "media_backup_*.tar.gz" -mtime +30 -delete
find "${BACKUP_DIR}" -name "media_backup_*.empty" -mtime +30 -delete

# Show backup directory contents
echo -e "${BLUE}📊 Current backups:${NC}"
ls -lh "${BACKUP_DIR}" | tail -n +2

echo -e "${GREEN}✨ Backup completed successfully at $(date)${NC}"
