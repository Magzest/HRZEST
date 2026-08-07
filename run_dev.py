#!/usr/bin/env python3
import os
import sys

# Pre-set environment variables for smooth local execution
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "dev-secret-key-12345")

from wsgi import app

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 HRMS Employee Attendance Platform — Development Server")
    print("="*60)
    print("📍 Local URLs to open in your web browser:")
    print("   • Employee Portal: http://127.0.0.1:5000/employee")
    print("   • Admin Employees: http://127.0.0.1:5000/employees")
    print("   • Health Check:    http://127.0.0.1:5000/healthz")
    print("="*60 + "\n")

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
