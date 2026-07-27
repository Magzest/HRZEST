#!/bin/bash
PROJ_DIR="/home/kali/.gemini/antigravity/scratch/employee-attendance-system"
cd "$PROJ_DIR"

# Clean up any stale sockets/locks if postgres isn't running properly
if ! /usr/lib/postgresql/18/bin/pg_ctl -D "$PROJ_DIR/pgdata" status >/dev/null 2>&1; then
    /usr/lib/postgresql/18/bin/pg_ctl -D "$PROJ_DIR/pgdata" stop -m immediate >/dev/null 2>&1 || true
    rm -f "$PROJ_DIR/pgdata/postmaster.pid" "/tmp/.s.PGSQL.5432" "/tmp/.s.PGSQL.5432.lock"
    /usr/lib/postgresql/18/bin/pg_ctl -D "$PROJ_DIR/pgdata" -o "-k /tmp" -l "$PROJ_DIR/pgdata/postgres.log" start
    sleep 2
fi

# Ensure postgres user and employee_attendance database exist
/usr/lib/postgresql/18/bin/psql -h /tmp -d postgres -c "CREATE USER postgres WITH SUPERUSER PASSWORD 'postgres';" 2>/dev/null || true
/usr/lib/postgresql/18/bin/psql -h /tmp -d postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';" 2>/dev/null || true
/usr/lib/postgresql/18/bin/createdb -h /tmp -U postgres employee_attendance 2>/dev/null || true

# Launch WSGI server
echo "Starting Employee Attendance System application..."
exec ./venv/bin/python wsgi.py

