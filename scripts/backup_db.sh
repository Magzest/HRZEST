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
# pg_dump prompts interactively for a password with no way to answer that
# in a cron/systemd-timer context (it just hangs) unless one of libpq's own
# non-interactive sources is set -- PGPASSWORD is the simplest for a
# script that already reads every other PG* value from the same place
# (.env, via the scheduling unit's EnvironmentFile=). Only exported when
# DB_PASS is actually set, so a host using trust auth or ~/.pgpass instead
# isn't forced to have DB_PASS defined too.
if [ -n "${DB_PASS:-}" ]; then
    export PGPASSWORD="${DB_PASS}"
fi

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

# Clean up local backups older than 30 days -- the offsite copy in S3
# (below) is the durable one; local retention here is just so a restore
# from "five minutes ago" doesn't need a network round trip, and so this
# directory doesn't grow unbounded on the app server's own disk.
echo "🧹 Cleaning up backups older than 30 days..."
find "${BACKUP_DIR}" -type f -name "db_backup_*.sql.gz" -mtime +30 -exec rm -f {} \;

# Upload offsite to S3 -- this is the actual durable copy. Local-only
# backups don't survive the host they're sitting on being lost, which is
# exactly the scenario a backup is meant to protect against.
#
# BACKUP_S3_BUCKET is required for the upload step; everything above still
# runs (and this script still exits 0) without it, so a host that hasn't
# been given the variable yet doesn't start failing its backup cron/timer
# outright -- but see RESTORE.md: a backup that never leaves this host is
# not a real backup, so treat an unset BACKUP_S3_BUCKET as a setup gap to
# close, not a supported long-term mode.
#
# Credentials: the AWS CLI resolves these itself in the usual order (env
# vars AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, ~/.aws/credentials, or --
# preferred, no static keys on the host at all -- the EC2 instance's own
# IAM role via instance metadata). This script never reads or handles
# credentials directly.
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
    S3_KEY="backups/db_backup_${TIMESTAMP}.sql.gz"
    echo "☁️  Uploading to s3://${BACKUP_S3_BUCKET}/${S3_KEY}..."
    if command -v aws >/dev/null 2>&1; then
        if aws s3 cp "${BACKUP_FILE}" "s3://${BACKUP_S3_BUCKET}/${S3_KEY}" \
            --only-show-errors \
            ${BACKUP_S3_STORAGE_CLASS:+--storage-class "${BACKUP_S3_STORAGE_CLASS}"}; then
            echo "✅ Offsite upload complete."
        else
            echo "❌ S3 upload failed! The local copy above still exists, but this backup is NOT yet offsite." >&2
            exit 1
        fi
    else
        echo "❌ aws CLI not found -- cannot upload to S3. Install awscli (pip install awscli, or apt/yum package) and re-run." >&2
        exit 1
    fi
else
    echo "⚠️  BACKUP_S3_BUCKET is not set -- backup stayed local-only at ${BACKUP_FILE}." >&2
    echo "   This host loses ALL its backups if it's ever lost. Set BACKUP_S3_BUCKET (see .env.example) before relying on this." >&2
fi

echo "🎉 Backup operation completed!"
