# Grade Change Intelligence — single-service image.
#
# The React app is built in a Node stage and copied into the Python stage, where
# FastAPI serves both the API and the static bundle. One container, one port, one
# origin, so CORS and a separate static host are out of the picture.

# ─── Stage 1: build the UI ────────────────────────────────────────────────────
FROM node:22-slim AS ui

WORKDIR /ui

# Copy manifests first so the dependency layer is cached independently of source.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Relative /api calls keep the bundle origin-agnostic; the API is same-origin.
ENV VITE_API_BASE_URL=""
RUN npm run build


# ─── Stage 2: API + models + static bundle ────────────────────────────────────
# 3.13 matches the devcontainer: the pinned numpy and scipy releases require
# Python >= 3.12, and 3.13 is the version this stack has actually been resolved
# against, so it is the safe target rather than the newest available.
FROM python:3.13-slim AS runtime

# Fail fast and log unbuffered so container logs show the model warm-up live.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# The validated model code and its datasets, unchanged.
COPY modules/ ./modules/
COPY data/ ./data/
COPY backend/ ./backend/

COPY --from=ui /ui/dist ./frontend/dist

# The feedback log is the only path written at runtime. On a host with an
# ephemeral filesystem it resets on redeploy; mount a volume here to keep it.
RUN mkdir -p /app/feedback_logs
VOLUME ["/app/feedback_logs"]

EXPOSE 8000

# Models train during startup (~25s), so the socket opens only once the service
# is genuinely ready — a health check that succeeds means it can serve traffic.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

WORKDIR /app/backend
# Single worker on purpose: each worker would train its own copy of the models,
# tripling memory and startup for no benefit at demo concurrency.
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
