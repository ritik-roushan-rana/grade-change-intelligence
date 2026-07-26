"""Filesystem wiring for the API.

The FastAPI service is a thin wrapper around the validated Python modules that
already live at the repository root (``modules/``). Nothing in that package is
modified or re-implemented here; this file only makes it importable and points
at the same CSVs the Streamlit dashboard reads.
"""

from __future__ import annotations

import os
import sys

# backend/gci_api/paths.py -> backend/gci_api -> backend -> <repo root>
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(PACKAGE_DIR)
REPO_ROOT = os.path.dirname(BACKEND_DIR)

# `modules` is a top-level package at the repo root, so the root has to be on
# sys.path before the model imports resolve.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DATA_DIR = os.path.join(REPO_ROOT, "data")
TIMESERIES_PATH = os.path.join(DATA_DIR, "grade_change_timeseries.csv")
SUMMARY_PATH = os.path.join(DATA_DIR, "grade_change_event_summary.csv")

FEEDBACK_LOG_DIR = os.environ.get(
    "FEEDBACK_LOG_DIR", os.path.join(REPO_ROOT, "feedback_logs")
)
FEEDBACK_LOG_PATH = os.path.join(FEEDBACK_LOG_DIR, "feedback_log.csv")

# Production build of the React app. When present, the API serves it directly so
# a deployment is a single service on a single origin; in local development the
# Vite dev server owns the UI instead and this stays absent.
FRONTEND_DIST = os.environ.get(
    "FRONTEND_DIST", os.path.join(REPO_ROOT, "frontend", "dist")
)


def frontend_build_present() -> bool:
    return os.path.isfile(os.path.join(FRONTEND_DIST, "index.html"))


def ensure_dirs() -> None:
    os.makedirs(FEEDBACK_LOG_DIR, exist_ok=True)


def data_files_present() -> bool:
    return os.path.exists(TIMESERIES_PATH) and os.path.exists(SUMMARY_PATH)
