#!/usr/bin/env bash
# ==============================================================================
# Automated PostgreSQL Backup Script — HRzest.com
# Runs pg_dump to create a compressed, timestamped backup in backups/
# Deletes backups older than 30 days automatically.
# ==============================================================================

set -euo pipefail

# Directory locations
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP="$(date +'%Y-%m-%d_%H-%M-%S')"
BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"

# Ensure backups directory exists
mkdir -p "${BACKUP_DIR}"

# Postgres connection variables (from environment or defaults)
PG_HOST="${DB_HOST:-127.0.0.1}"
PG_PORT="${DB_PORT:-5432}"
PG_USER="${DB_USER:-postgres}"
PG_NAME="${DB_NAME:-postgres}"

echo "📦 Starting PostgreSQL database backup..."
echo "   Database: ${PG_NAME} @ ${PG_HOST}:${PG_PORT}"
echo "   Target:   ${BACKUP_FILE}"

# Execute pg_dump and compress with gzip
if pg_dump -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" "${PG_NAME}" | gzip > "${BACKUP_FILE}"; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "✅ Backup successfully created! File size: ${SIZE}"
else
    echo "❌ pg_dump failed! Attempting socket backup..."
    if pg_dump -h /tmp -p "${PG_PORT}" -U "${PG_USER}" "${PG_NAME}" 2>/dev/null | gzip > "${BACKUP_FILE}"; then
        SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
        echo "✅ Backup successfully created via socket! File size: ${SIZE}"
    else
        echo "❌ Backup failed!"
        exit 1
    fi
fi

# Clean up backups older than 30 days
echo "🧹 Cleaning up backups older than 30 days..."
find "${BACKUP_DIR}" -type f -name "db_backup_*.sql.gz" -mtime +30 -exec rm -f {} \;
echo "🎉 Backup operation completed!"
