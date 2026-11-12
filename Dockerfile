# Dockerfile for DMS FastAPI Backend
# Multi-stage build for production: builder installs deps, final stage runs the app
#
# Build: docker build -t dms-backend .
# Run:  docker run -d --name dms-backend --env-file .env -p 8000:8000 dms-backend
#
# OR via docker-compose (see docker-compose.yml)

FROM python:3.11-slim AS builder

# ───── Environment & working directory ─────
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ───── System dependencies (OS-level) ─────
# Install just what's needed: postgresql client for psycopg2, plus tzdata
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# ───── Install Python dependencies ─────
# Copy requirements first for layer caching
COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

# ───── Copy application code ─────
COPY backend /app

# ───── Final stage ─────
FROM python:3.11-slim

# Create app user (non-root for security)
RUN addgroup --system app && adduser --system --ingroup app app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.local/bin:${PATH}"

WORKDIR /app

# Copy installed wheels from builder
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code (source files)
COPY --from=builder /app /app

# Ensure proper ownership
RUN chown -R app:app /app

# Non-root user
USER app

# ───── Expose port ─────
EXPOSE 8000

# ───── Startup command ─────
# Apply database migrations then start the server
# In production: DEBUG=false + alembic; in dev: lifespan handles table creation
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]