# gunicorn.conf.py — Production WSGI server configuration
# Loaded automatically: gunicorn -c gunicorn.conf.py wsgi:application

import multiprocessing
import os

# ── Binding ──────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# ── Workers ──────────────────────────────────────────────────────────────────
# gthread: multi-threaded workers — ideal for I/O-bound face recognition
# Rule of thumb: (2 × CPU cores) + 1, capped at 8 for a 4 GB VPS
workers = min((multiprocessing.cpu_count() * 2) + 1, 8)
worker_class = "gthread"
threads = 4          # threads per worker
worker_connections = 1000

# ── Timeouts ─────────────────────────────────────────────────────────────────
# Face-recognition encoding can take 3-6 s on CPU
timeout = 120
graceful_timeout = 30
keepalive = 5

# ── Memory leak prevention ───────────────────────────────────────────────────
# Restart each worker after this many requests to prevent slow leaks from
# face_recognition / numpy / cv2 object accumulation
max_requests = 1000
max_requests_jitter = 100   # random jitter so workers don't all restart at once

# ── Logging ──────────────────────────────────────────────────────────────────
accesslog = "-"             # stdout → Docker / systemd captures it
errorlog  = "-"             # stderr
loglevel  = os.environ.get("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# ── Process naming ───────────────────────────────────────────────────────────
proc_name = "hrms-attendance"

# ── Security ─────────────────────────────────────────────────────────────────
limit_request_line       = 4096
limit_request_fields     = 100
limit_request_field_size = 8190

# ── Server hooks ─────────────────────────────────────────────────────────────
def on_starting(server):
    server.log.info("🚀 HRzest.com — Gunicorn starting")

def worker_exit(server, worker):
    server.log.info(f"Worker {worker.pid} exited cleanly")
