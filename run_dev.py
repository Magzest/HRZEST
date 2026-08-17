# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import os
import sys

# Pre-set environment variables for smooth local execution
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "dev-secret-key-12345")

from wsgi import app

# Local-only: skip the mandatory admin TOTP enrollment gate so the app is
# reachable without an authenticator app during local dev/testing.
app.config["MANDATORY_ADMIN_MFA"] = False

if __name__ == "__main__":
    # Same cert-detection pattern as wsgi.py's own __main__ block -- kept
    # in sync here since run_dev.py is a separate entrypoint that imports
    # wsgi's `app` directly rather than executing wsgi.py itself, so that
    # block never runs when launching via `python run_dev.py`.
    port = int(os.environ.get("PORT", 5000))
    _cert = os.environ.get("SSL_CERT_PATH") or os.path.join(os.path.dirname(__file__), "cert.pem")
    _key = os.environ.get("SSL_KEY_PATH") or os.path.join(os.path.dirname(__file__), "key.pem")
    _https = os.path.exists(_cert) and os.path.exists(_key)
    _scheme = "https" if _https else "http"

    print("\n" + "="*60)
    print("🚀 HRzest.com -- Development Server")
    print("="*60)
    print(f"📍 Local URLs to open in your web browser (Port {port}):")
    print(f"   • Login Page:      {_scheme}://127.0.0.1:{port}/login")
    print(f"   • Admin Dashboard: {_scheme}://127.0.0.1:{port}/admin")
    print(f"   • Employee Portal: {_scheme}://127.0.0.1:{port}/employee_portal")
    print(f"   • Health Check:    {_scheme}://127.0.0.1:{port}/healthz")
    if not _https:
        print("\n⚠   No cert.pem / key.pem found -- run `python generate_cert.py` for HTTPS.")
    print("="*60 + "\n")

    # threaded=True matters here: /api/session/risk-stream (blueprints/
    # core.py) holds an SSE connection open for ~20s, and Werkzeug's dev
    # server is single-threaded by default -- without this, one open
    # stream blocks every other request on the server until it closes,
    # which is exactly what produced the ERR_TIMED_OUT/"took too long to
    # respond" browser error.
    if _https:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True, ssl_context=(_cert, _key))
    else:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
