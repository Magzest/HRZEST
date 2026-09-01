# -*- coding: utf-8 -*-
"""Background job queue for heavy work (PDF/Excel generation today) --
Redis-backed via RQ when configured, synchronous fallback otherwise.

Why this exists: blueprints/attendance.py, payroll.py, performance.py
(openpyxl) and onboarding.py (reportlab) all build their export file
in-request, on the same worker thread handling the HTTP request, then
return it directly via send_file(). For a large company (thousands of
employees, a year of attendance) that can hold a worker thread for
several seconds -- fine at today's scale, a real bottleneck once a
deployment runs a small, fixed number of sync worker processes (e.g.
gunicorn -w 4) and several big exports land at once.

This module provides the queue primitive (enqueue_or_run) but
deliberately does NOT convert any of those four existing endpoints on
its own. They all return the generated file synchronously as the HTTP
response body -- true async execution means the file doesn't exist yet
when the request that kicked it off returns, so the API contract has to
change too: the endpoint would need to return a job id immediately, and
the caller (web JS, and the mobile app's matching Bearer-token routes
added this session for payroll/salary reports) would need to poll a
status endpoint and then download once ready. That's a UX/API design
decision for whoever owns those flows, not something to silently change
out from under existing callers as a "fix this flaw" pass. Wire a
specific endpoint through enqueue_or_run() once that contract is decided.

Local dev / any deployment without REDIS_URL configured: everything
runs exactly as it does today, synchronously, in the calling thread --
enqueue_or_run() just calls the function directly and returns its
result. No behavior change until REDIS_URL is set AND a worker process
is actually running (`rq worker` -- see the note on run_worker() below).
"""
import os


def queue_configured():
    """True if a Redis-backed queue should be used. The single source of
    truth every function below checks first."""
    return bool(os.environ.get("REDIS_URL") or os.environ.get("REDIS_HOST"))


def _redis_conn():
    import redis
    url = os.environ.get("REDIS_URL")
    if url:
        return redis.from_url(url)
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD") or None,
    )


def get_queue(name="default"):
    """Returns an RQ Queue bound to the configured Redis connection.
    Raises if queue_configured() is False -- callers should check that
    first (enqueue_or_run() below does this for you)."""
    from rq import Queue
    return Queue(name, connection=_redis_conn())


def enqueue_or_run(fn, *args, queue_name="default", **kwargs):
    """The one function most callers need: enqueues fn(*args, **kwargs)
    as a background RQ job when a queue is configured, otherwise just
    calls it directly and returns its result immediately.

    Return value differs by mode, which is exactly why this isn't a
    drop-in replacement for a direct call inside a request handler that
    needs the result to build its HTTP response NOW:
      - Sync fallback (no queue configured): returns fn's actual return
        value, immediately.
      - Queued: returns an rq.job.Job -- the caller gets `.id` to persist
        (e.g. in a DB row) and hand back to the client, then later calls
        fetch_job(job_id) to poll for completion. fn's return value isn't
        available at all until the job finishes, on a different process.

    Pick your calling code accordingly: an endpoint that must return the
    finished file in this same response should keep calling fn() directly
    (this function's sync-fallback behavior IS that direct call) rather
    than reaching for this at all unless it's also been redesigned around
    a job-id + poll flow."""
    if not queue_configured():
        return fn(*args, **kwargs)
    return get_queue(queue_name).enqueue(fn, *args, **kwargs)


def fetch_job(job_id, queue_name="default"):
    """Look up a previously-enqueued job by id. Returns None if RQ/Redis
    isn't configured (nothing to look up) or the job id is unknown/expired.
    Check job.is_finished / job.is_failed / job.result on what's returned."""
    if not queue_configured():
        return None
    from rq.job import Job
    try:
        return Job.fetch(job_id, connection=_redis_conn())
    except Exception:
        return None


def run_worker(queue_names=("default",)):
    """Blocking RQ worker loop -- run this as its own separate process
    (`python -c "from utils.task_queue import run_worker; run_worker()"`,
    or a dedicated `rq worker` CLI invocation once actual jobs are being
    enqueued), never inside the Flask app process itself. No-ops
    immediately if no queue is configured, so this is safe to leave in a
    startup script unconditionally."""
    if not queue_configured():
        return
    from rq import Worker
    conn = _redis_conn()
    worker = Worker(list(queue_names), connection=conn)
    worker.work()
