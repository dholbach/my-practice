#!/bin/bash
#
# Backup script for Payments System
# Creates timestamped backups of PostgreSQL database and media files
#
# Media and backups are stored OUTSIDE the git repository.
# Set MY_PRACTICE_DATA_DIR in .env or environment to control the location.
# Default: <parent of repo>/payments-data
#

set -e

# Resolve paths relative to this script so the script works regardless of cwd
# (e.g. when called by systemd with an arbitrary working directory).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment variables from repo root .env
if [ -f "${REPO_DIR}/.env" ]; then
    export $(grep -v '^#' "${REPO_DIR}/.env" | xargs)
fi

# Set defaults if not in .env
POSTGRES_DB=${POSTGRES_DB:-my_practice}
POSTGRES_USER=${POSTGRES_USER:-my_practice}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-changeme123}

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

echo -e "${BLUE}📦 Starting backup at $(date)${NC}"
echo -e "${BLUE}   Data directory: ${MY_PRACTICE_DATA_DIR}${NC}"

# Ensure backup directory exists (creates MY_PRACTICE_DATA_DIR/backups if needed)
mkdir -p "${BACKUP_DIR}"

# docker compose must be called from the repo directory
cd "$REPO_DIR"

echo -e "${BLUE}🗄️  Backing up PostgreSQL database...${NC}"

# Backup PostgreSQL database using docker exec
flatpak-spawn --host docker compose exec -T postgres pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --no-owner \
    --clean \
    --if-exists \
    | gzip > "${DB_BACKUP_FILE}"

if [ $? -eq 0 ]; then
    DB_SIZE=$(du -h "${DB_BACKUP_FILE}" | cut -f1)
    echo -e "${GREEN}✅ Database backup complete: ${DB_BACKUP_FILE} (${DB_SIZE})${NC}"
else
    echo -e "${RED}❌ Database backup failed${NC}"
    exit 1
fi

echo -e "${BLUE}📁 Backing up media files...${NC}"

# Backup media files from Docker volume
# First, check if media volume has any data
MEDIA_COUNT=$(flatpak-spawn --host docker compose exec -T django find /app/media -type f 2>/dev/null | wc -l)

if [ "${MEDIA_COUNT}" -gt 0 ]; then
    flatpak-spawn --host docker compose exec -T django tar czf - -C /app media \
        > "${MEDIA_BACKUP_FILE}"

    if [ $? -eq 0 ]; then
        MEDIA_SIZE=$(du -h "${MEDIA_BACKUP_FILE}" | cut -f1)
        echo -e "${GREEN}✅ Media backup complete: ${MEDIA_BACKUP_FILE} (${MEDIA_SIZE})${NC}"
    else
        echo -e "${RED}❌ Media backup failed${NC}"
        exit 1
    fi
else
    echo -e "${BLUE}ℹ️  No media files to backup${NC}"
    # Create empty marker file
    echo "No media files at $(date)" > "${MEDIA_BACKUP_FILE}.empty"
fi

# Cleanup old backups (keep last 30 days)
echo -e "${BLUE}🧹 Cleaning up old backups (keeping last 30 days)...${NC}"
find "${BACKUP_DIR}" -name "db_backup_*.sql.gz" -mtime +30 -delete
find "${BACKUP_DIR}" -name "media_backup_*.tar.gz" -mtime +30 -delete
find "${BACKUP_DIR}" -name "media_backup_*.empty" -mtime +30 -delete

# Show backup directory contents
echo -e "${BLUE}📊 Current backups:${NC}"
ls -lh "${BACKUP_DIR}" | tail -n +2

echo -e "${GREEN}✨ Backup completed successfully at $(date)${NC}"
