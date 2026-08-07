#!/usr/bin/env python3
import os
import sys

# Pre-set environment variables for smooth local execution
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "dev-secret-key-12345")

from wsgi import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("\n" + "="*60)
    print("🚀 HRzest.com — Development Server")
    print("="*60)
    print(f"📍 Local URLs to open in your web browser (Port {port}):")
    print(f"   • Login Page:      http://127.0.0.1:{port}/login")
    print(f"   • Admin Dashboard: http://127.0.0.1:{port}/admin")
    print(f"   • Employee Portal: http://127.0.0.1:{port}/employee_portal")
    print(f"   • Health Check:    http://127.0.0.1:{port}/healthz")
    print("="*60 + "\n")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
