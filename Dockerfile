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
COPY scripts/build_model_cache.py ./scripts/build_model_cache.py

# Train here, once, instead of on every cold start. Fitting the Random Forest
# and the Gradient Boosting regressor is ~22 of the ~25 startup seconds, and the
# result depends only on the CSVs above — on a throttled shared-CPU host that
# same work took minutes and every sleeping instance paid it again. The API
# reloads these fitted objects in ~0.3s and falls back to training if the
# artifact does not match the data it is serving.
RUN python scripts/build_model_cache.py

COPY --from=ui /ui/dist ./frontend/dist

# The feedback log is the only path written at runtime. World-writable because
# some hosts (Hugging Face Spaces, for one) run the container as a non-root UID.
# On a host with an ephemeral filesystem it resets on redeploy; mount a volume
# here, or point FEEDBACK_LOG_DIR at one, to keep it.
RUN mkdir -p /app/feedback_logs && chmod 777 /app/feedback_logs
VOLUME ["/app/feedback_logs"]

# 8000 is the default; hosts that inject PORT (Render) or expect another port
# (Spaces, via app_port) are honoured by the CMD below.
EXPOSE 8000

# The socket opens only once the models are loaded, so a passing health check
# means the service can actually serve traffic.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; port=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health').status==200 else 1)"

WORKDIR /app/backend
# Single worker on purpose: each worker would load its own copy of the models,
# tripling memory for no benefit at demo concurrency.
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
