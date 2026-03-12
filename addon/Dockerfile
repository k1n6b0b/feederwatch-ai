# FeederWatch AI Add-on — Multi-stage Dockerfile
#
# Stage 1: Build React + TypeScript frontend
# Stage 2: Python 3.12 runtime (no Node, no build tools in final image)

# ── Stage 1: Frontend build ────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend

# Install dependencies first (layer cache)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source and build
COPY frontend/ .
RUN npm run build
# Output: /build/frontend/dist/


# ── Stage 2: Python runtime ────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# System deps for Pillow and litert
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libjpeg-turbo-progs \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY src/ ./src/

# Frontend build artifacts from stage 1
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Persistent data directory (mounted by HA Supervisor)
RUN mkdir -p /data/snapshots

ENV FEEDERWATCH_DB=/data/feederwatch.db \
    FEEDERWATCH_STATIC=/app/frontend/dist \
    FEEDERWATCH_LABELS=/data/labels.txt \
    FEEDERWATCH_HOST=0.0.0.0 \
    FEEDERWATCH_PORT=8099

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8099/api/v1/status')"

CMD ["python", "-m", "src.main"]
