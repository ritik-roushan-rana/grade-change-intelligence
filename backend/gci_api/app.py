"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import paths
from .api import router
from .registry import registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gci")

# The Vite dev server runs on a different port, so the browser treats API calls
# as cross-origin. Defaults cover Vite's default port and its preview port on
# both loopback spellings; override with CORS_ORIGINS (comma-separated).
DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def _allowed_origins() -> list[str]:
    configured = os.environ.get("CORS_ORIGINS", "").strip()
    if not configured:
        return DEFAULT_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Data, correlation suite, both models and the KNN library are built once
    # here rather than per request.
    log.info("Warming up Grade Change Intelligence ...")
    registry.load()
    log.info(
        "Models ready (%ss). %d events, %d recovery patterns.",
        registry.startup_seconds,
        registry.summary_df["grade_change_event_id"].nunique(),
        registry.recovery_pattern_count,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Grade Change Intelligence API",
        description=(
            "REST interface over the Honeywell QCS grade-change models: "
            "Random Forest risk classifier, Gradient Boosting deviation "
            "regressor, KNN recovery recommender, correlation analysis and "
            "recipe limits."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.exception_handler(FileNotFoundError)
    async def missing_data_handler(request, exc: FileNotFoundError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app from this service, when a build exists.

    Registered after the API router so /api and /docs always win. The catch-all
    returns index.html for unknown paths because the UI uses client-side
    routing: a cold request to /correlations has no file behind it and must be
    answered with the shell so the router can take over.
    """
    if not paths.frontend_build_present():
        log.info("No frontend build at %s — serving API only.", paths.FRONTEND_DIST)

        @app.get("/")
        def api_root():
            return {
                "service": "Grade Change Intelligence API",
                "docs": "/docs",
                "health": "/api/health",
            }

        return

    index_file = os.path.join(paths.FRONTEND_DIST, "index.html")

    # Vite emits every hashed asset and bundled font under /assets.
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(paths.FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/{spa_path:path}", include_in_schema=False)
    def spa(spa_path: str):
        # An unmatched /api path is a genuine 404, not a display route; without
        # this, a mistyped endpoint would return the HTML shell and the client
        # would fail on JSON parsing instead of reporting the real status.
        if spa_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Unknown API endpoint.")
        candidate = os.path.normpath(os.path.join(paths.FRONTEND_DIST, spa_path))
        if (
            spa_path
            and candidate.startswith(paths.FRONTEND_DIST)
            and os.path.isfile(candidate)
        ):
            return FileResponse(candidate)
        return FileResponse(index_file)

    log.info("Serving frontend build from %s", paths.FRONTEND_DIST)
