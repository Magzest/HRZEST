# ==============================================================================
# Production Dockerfile — HRzest.com Backend & Web UI
# ==============================================================================

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
# - gcc / libpq-dev:         psycopg2 compilation
# - netcat-openbsd:          entrypoint.sh DB health check (nc -z)
# - cmake / g++ / make / libboost-all-dev / libopenblas-dev / liblapack-dev /
#   libx11-dev / libssl-dev / pkg-config: build dlib for face-recognition
#   (dlib is C++ — cmake alone can't build it without an actual compiler and
#   build driver; see Containerfile's builder stage for the same set)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    curl \
    netcat-openbsd \
    cmake \
    libboost-all-dev \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer — only rebuilds when requirements change)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application source
COPY . ./

# Make scripts executable
RUN chmod +x entrypoint.sh

# Create a non-root user for security hardening
# (never run production containers as root)
RUN useradd -m -u 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

ENTRYPOINT ["./entrypoint.sh"]
