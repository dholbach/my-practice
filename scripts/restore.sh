#!/bin/bash
#
# Restore script for Payments System
# Restores PostgreSQL database and media files from backup
#

set -e

# Resolve paths relative to this script so the script works regardless of cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables from repo root .env
if [ -f "${REPO_DIR}/.env" ]; then
    export $(grep -v '^#' "${REPO_DIR}/.env" | xargs)
fi

# External data directory (must match MY_PRACTICE_DATA_DIR in .env / backup.sh)
MY_PRACTICE_DATA_DIR="${MY_PRACTICE_DATA_DIR:-$(dirname "$REPO_DIR")/my-practice-data}"
BACKUP_DIR="${MY_PRACTICE_DATA_DIR}/backups"

# Check if backup file is provided
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <db_backup_file> [media_backup_file]${NC}"
    echo ""
    echo "Example:"
    echo "  $0 ${BACKUP_DIR}/db_backup_20250115_120000.sql.gz"
    echo "  $0 ${BACKUP_DIR}/db_backup_20250115_120000.sql.gz ${BACKUP_DIR}/media_backup_20250115_120000.tar.gz"
    echo ""
    echo "Available backups (${BACKUP_DIR}):"
    ls -lh "${BACKUP_DIR}" 2>/dev/null | grep -E "(db_backup|media_backup)" || echo "  No backups found"
    exit 1
fi

DB_BACKUP_FILE="$1"
MEDIA_BACKUP_FILE="${2:-}"

# Check if database backup file exists
if [ ! -f "${DB_BACKUP_FILE}" ]; then
    echo -e "${RED}❌ Database backup file not found: ${DB_BACKUP_FILE}${NC}"
    exit 1
fi

# Set defaults if not in .env
POSTGRES_DB=${POSTGRES_DB:-my_practice}
POSTGRES_USER=${POSTGRES_USER:-my_practice}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-changeme123}

# docker compose must be called from the repo directory
cd "$REPO_DIR"

echo -e "${YELLOW}⚠️  WARNING: This will OVERWRITE the current database!${NC}"
echo -e "${YELLOW}   Database: ${POSTGRES_DB}${NC}"
echo -e "${YELLOW}   Backup file: ${DB_BACKUP_FILE}${NC}"
if [ -n "${MEDIA_BACKUP_FILE}" ]; then
    echo -e "${YELLOW}   Media file: ${MEDIA_BACKUP_FILE}${NC}"
fi
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo -e "${BLUE}Restore cancelled.${NC}"
    exit 0
fi

echo -e "${BLUE}🔄 Starting restore at $(date)${NC}"

# Restore PostgreSQL database
echo -e "${BLUE}🗄️  Restoring PostgreSQL database...${NC}"

gunzip -c "${DB_BACKUP_FILE}" | flatpak-spawn --host docker compose exec -T postgres psql \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --quiet

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database restore complete${NC}"
else
    echo -e "${RED}❌ Database restore failed${NC}"
    exit 1
fi

# Restore media files if provided
if [ -n "${MEDIA_BACKUP_FILE}" ] && [ -f "${MEDIA_BACKUP_FILE}" ]; then
    echo -e "${BLUE}📁 Restoring media files...${NC}"

    # Extract media files into Django container
    flatpak-spawn --host docker compose exec -T django sh -c "rm -rf /app/media/* && tar xzf - -C /app" \
        < "${MEDIA_BACKUP_FILE}"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Media restore complete${NC}"
    else
        echo -e "${RED}❌ Media restore failed${NC}"
        exit 1
    fi
else
    echo -e "${BLUE}ℹ️  No media backup to restore${NC}"
fi

echo -e "${GREEN}✨ Restore completed successfully at $(date)${NC}"
echo -e "${BLUE}💡 You may need to restart the Django container:${NC}"
echo -e "   docker compose restart django"
