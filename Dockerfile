
# =========================================================
# STAGE 1: BUILDER
# =========================================================
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create isolated Python environment
RUN python -m venv /opt/venv

# Install Python dependencies
COPY requirements.txt ./

RUN /opt/venv/bin/pip install \
    --no-cache-dir \
    -r requirements.txt


# =========================================================
# STAGE 2: RUNTIME
# =========================================================
FROM python:3.12-slim-bookworm AS runtime

# Python runtime configuration
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and upload directories
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p \
        /app/static/uploads/media \
        /app/static/uploads/private \
    && chown -R appuser:appuser /app/static

# Copy installed Python packages from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY --chown=appuser:appuser app.py alembic.ini ./
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser alembic/ ./alembic/

# Run as non-root user
USER appuser

# Application port
EXPOSE 8000

# Health check (requires GET /health returning HTTP 200)
HEALTHCHECK --interval=30s \
            --timeout=5s \
            --start-period=30s \
            --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# Start FastAPI application
CMD ["uvicorn", "app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]
