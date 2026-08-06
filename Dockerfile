# ==============================================================================
# Production Dockerfile — Employee Attendance Platform Backend & Web UI
# ==============================================================================

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    netcat-openbsd \
    cmake \
    libopenblas-dev \
    libdlib-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application source code
COPY . ./

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

ENTRYPOINT ["./entrypoint.sh"]
