import os
import re
import time
import logging
import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()
_HASHI_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashi", ".env")
load_dotenv(_HASHI_ENV)

_log = logging.getLogger("attendance")
# Logger is configured in app.py; database.py uses the same named logger so
# output is consistent without adding a second handler here.

# sslmode: "prefer" encrypts the connection whenever the server supports it
# (RDS always does) but degrades gracefully to plaintext otherwise, so local
# Postgres installs without SSL configured (e.g. this repo's dev setup)
# still work. Set DB_SSLMODE=require (or verify-full, with DB_SSLROOTCERT
# pointing at the RDS CA bundle) for a stricter production posture.
#
# statement_timeout bounds how long any single query may run — without it, a
# slow/runaway query (buggy report filter, or a deliberate DoS attempt) can
# hold a connection — and with only `maxconn=20` in the pool, a handful of
# stuck queries is enough to starve every other request of a connection.
# connect_timeout bounds how long establishing a new connection may hang if
# the DB host is unreachable, instead of blocking a worker indefinitely.
_DB_CONFIG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASS", ""),
    dbname=os.environ.get("DB_NAME", "employee_attendance"),
    sslmode=os.environ.get("DB_SSLMODE", "prefer"),
    connect_timeout=int(os.environ.get("DB_CONNECT_TIMEOUT", "10")),
    options=f"-c statement_timeout={int(os.environ.get('DB_STATEMENT_TIMEOUT_MS', '30000'))}",
)
if os.environ.get("DB_SSLROOTCERT"):
    _DB_CONFIG["sslrootcert"] = os.environ["DB_SSLROOTCERT"]


class _PooledConnection:
    """Wraps a psycopg2 pooled connection so `.close()` returns it to the
    pool (via putconn) instead of actually closing it — psycopg2 pools
    require that explicitly, unlike mysql-connector's pooled connections
    where `.close()` already did this. The rest of the codebase's ~240
    call sites all do `db = get_db_connection(); ...; db.close()`, so
    wrapping here avoids rewriting every one of them.

    Also absorbs `buffered=`/`dictionary=` kwargs on .cursor() — both are
    mysql-connector-only options with no psycopg2 equivalent (psycopg2
    cursors are effectively buffered client-side by default), so this
    keeps the ~230 existing `cursor(buffered=True)` call sites working
    unchanged instead of needing every one edited.
    """
    __slots__ = ("_pool", "_conn")

    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn

    def cursor(self, *args, **kwargs):
        kwargs.pop("buffered", None)
        kwargs.pop("dictionary", None)
        return self._conn.cursor(*args, **kwargs)

    def close(self):
        if self._conn is not None:
            self._pool.putconn(self._conn)
            self._conn = None

    def __del__(self):
        # Safety net for the ~200 call sites that do `db = get_db_connection();
        # ...; db.close()` with no try/finally: if a handler raises before
        # reaching .close(), CPython drops this object's refcount to zero as
        # soon as the local variable goes out of scope (no reference cycle
        # here), running __del__ right away — return the connection to the
        # pool instead of leaking it out of circulation forever. Not a
        # substitute for closing explicitly (GC timing isn't guaranteed on
        # every Python implementation), just a backstop for the common case.
        try:
            self.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _set_search_path(conn, schema_name):
    """Switch a pooled connection's search_path to the given tenant schema.
    Equivalent to MySQL's `USE <db>` from the old design, but scoped to a
    schema within one shared Postgres database instead of a separate
    physical database per tenant (Postgres has no mid-connection USE)."""
    if not re.match(r'^[a-zA-Z0-9_]+$', schema_name):
        raise ValueError(f"Invalid tenant schema name: {schema_name!r}")
    cur = conn.cursor()
    cur.execute(f'SET search_path TO "{schema_name}", public')
    cur.close()


# ── Default tenant pool ──────────────────────────────────────────────────────
_pool = None


def _create_pool(retries=5, delay=3):
    global _pool
    for attempt in range(1, retries + 1):
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                **_DB_CONFIG,
            )
            _log.info('"Connected to PostgreSQL (attempt %d)"', attempt)
            return
        except psycopg2.Error as e:
            _log.warning('"PostgreSQL not ready (attempt %d/%d): %s"', attempt, retries, e)
            if attempt < retries:
                time.sleep(delay)
    raise RuntimeError("[DB] Could not connect to PostgreSQL after several retries. Is PostgreSQL running?")


def pool_stats():
    """Best-effort snapshot of connection pool utilization, for the Security
    hub's performance panel. psycopg2 exposes no public API for this, so it
    reads the pool's own bookkeeping (_used/_pool) — safe read-only access,
    never mutated here."""
    if _pool is None:
        return {"active": 0, "idle": 0, "max": 0}
    try:
        return {"active": len(_pool._used), "idle": len(_pool._pool), "max": _pool.maxconn}
    except Exception:
        return {"active": 0, "idle": 0, "max": 0}


def _borrow_connection():
    """Get a connection from the pool (building/rebuilding it as needed) with
    autocommit on. MySQL sessions default to autocommit (this app relies on
    that — most writes never call .commit()). psycopg2 connections default to
    autocommit=False, where a single failed statement aborts the whole
    transaction and poisons the connection for every future borrower once
    it's returned to the pool, so autocommit is set explicitly here to match
    MySQL's behavior."""
    global _pool
    if _pool is None:
        _create_pool()
    try:
        conn = _pool.getconn()
    except psycopg2.Error:
        # Pool went stale — rebuild it once and retry
        _pool = None
        _create_pool(retries=3, delay=2)
        conn = _pool.getconn()
    conn.autocommit = True
    return conn


def get_db_connection():
    """Return a connection for the current tenant (or the default "public" schema).

    Checks flask.g.tenant_db if Flask is active, then falls back to "public".
    Import of flask.g is done lazily to avoid circular imports.

    Always explicitly resets search_path on every borrow, even for the
    default (non-tenant) case — a pooled connection can come back from any
    previous borrower, including ones (like init_master_db/get_tenant_db)
    that pointed it at a tenant schema. Skipping the reset "because it's
    already the default" assumes the connection's history, which isn't a
    safe assumption for a shared pool; that assumption previously caused
    tenant schema search_paths to leak onto unrelated borrows.
    """
    tenant_db = None
    try:
        from flask import g as _flask_g
        tenant_db = getattr(_flask_g, "tenant_db", None)
    except RuntimeError:
        # Outside of a Flask application context — skip g lookup
        pass

    conn = _borrow_connection()
    _set_search_path(conn, tenant_db or "public")
    return _PooledConnection(_pool, conn)


# ── Master DB (tenant registry) ──────────────────────────────────────────────
# Postgres has no mid-connection database switch, so the tenant registry now
# lives as its own schema in the same physical database as everything else,
# rather than a second physical MySQL database (att_master).
_MASTER_SCHEMA = "att_master"


def get_master_db():
    """Return a connection scoped to the att_master tenant-registry schema."""
    conn = _borrow_connection()
    _set_search_path(conn, _MASTER_SCHEMA)
    return _PooledConnection(_pool, conn)


# ── Tenant DB helper ─────────────────────────────────────────────────────────

def get_tenant_db(schema_name: str):
    """Return a pooled connection switched to the given tenant schema.

    schema_name is validated against ^[a-zA-Z0-9_]+$ before use (in
    _set_search_path) to prevent injection via the SET search_path statement.
    """
    conn = _borrow_connection()
    _set_search_path(conn, schema_name)
    return _PooledConnection(_pool, conn)


# ── Tenant schema provisioning ────────────────────────────────────────────────

def create_tenant_schema(schema_name: str):
    """Create a new tenant schema in the shared Postgres database.

    Validates schema_name before use. Replaces the old create_tenant_database()
    — tenants are now schemas within one database, not separate MySQL
    databases (Postgres can't switch databases mid-connection the way MySQL's
    USE did, so schema-per-tenant is the equivalent isolation model).
    """
    if not re.match(r'^[a-zA-Z0-9_]+$', schema_name):
        raise ValueError(f"Invalid tenant schema name: {schema_name!r}")
    if _pool is None:
        _create_pool()
    conn = _pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        conn.commit()
        cur.close()
        _log.info('"Created tenant schema: %s"', schema_name)
    finally:
        _pool.putconn(conn)


# Kept as an alias so any not-yet-updated call sites fail loudly and
# obviously rather than silently doing the wrong thing.
def create_tenant_database(db_name: str):
    raise RuntimeError(
        "create_tenant_database() was replaced by create_tenant_schema() — "
        "tenants are Postgres schemas now, not separate databases."
    )


@contextmanager
def transaction(conn):
    """Wrap a block of multi-statement writes in one explicit transaction
    instead of _borrow_connection()'s default per-statement autocommit.

    Needed wherever several related INSERT/UPDATE/DELETE statements must
    all succeed or all fail together (e.g. deleting an employee's rows
    across several tables) — under autocommit, a failure partway through
    leaves the earlier statements permanently committed instead of rolled
    back. Accepts either a _PooledConnection wrapper or a raw psycopg2
    connection; always restores autocommit=True afterwards so the
    connection behaves as every other borrower of this pool expects.
    """
    raw = getattr(conn, "_conn", conn)
    raw.autocommit = False
    try:
        yield conn
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.autocommit = True
