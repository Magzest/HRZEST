#!/usr/bin/env bash
set -e

echo "🚀 Starting Employee Attendance Platform Container..."

# Wait for PostgreSQL to be ready if DB_HOST is set
if [ -n "$DB_HOST" ]; then
    echo "⏳ Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    while ! curl -s http://$DB_HOST:${DB_PORT:-5432} > /dev/null 2>&1 && ! nc -z $DB_HOST ${DB_PORT:-5432} 2>/dev/null; do
        sleep 1
    done
    echo "✅ PostgreSQL is reachable!"
fi

# Run Database Schema Migration
echo "📦 Running plan database migration..."
python migrate_plans.py || true

# Start Gunicorn WSGI Server
echo "🔥 Launching Gunicorn WSGI server on port 5000..."
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 --timeout 120 wsgi:application
