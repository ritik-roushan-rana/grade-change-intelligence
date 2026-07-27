"""Persisted training artifacts, so a cold start does not retrain the models.

Training is the whole cold start: on a developer machine the Random Forest and
Gradient Boosting fits take ~22 of the ~25 startup seconds, and on a throttled
free-tier CPU the same work stretched to minutes. None of it depends on the
request — the same CSVs produce the same fitted models every time — so it is
done once (at image build time) and the fitted objects are reloaded here.

Only the *expensive* state is stored. The model classes re-read their CSVs in
``__init__`` in about 50 ms, so the frames are left out of the payload and the
cache stays small.

The cache is keyed by a fingerprint of everything that could change the fitted
result: the datasets, the model source files, and the library versions that
pickled the estimators. A mismatch means the cache is silently ignored and the
models train as before, so a stale artifact can never serve wrong predictions.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
import sklearn

from . import paths

log = logging.getLogger("gci.cache")

# Bump when the payload layout or the restored attribute set changes.
CACHE_VERSION = 3

ARTIFACT_DIR = os.environ.get(
    "ARTIFACT_DIR", os.path.join(paths.REPO_ROOT, "artifacts")
)
CACHE_PATH = os.path.join(ARTIFACT_DIR, "model_cache.joblib")

# Attributes that carry fitted state. Everything else on the instances is
# rebuilt by their constructors.
_MODEL_ATTRS = (
    "classifier",
    "regressor",
    "label_encoder",
    "feature_columns",
    "train_event_ids",
    "test_event_ids",
    "evaluation_results",
    "_trained",
)
_ENGINE_ATTRS = (
    "recovery_library",
    "knn_model",
    "scaler",
    "_built",
)

_SOURCE_FILES = (
    os.path.join(paths.REPO_ROOT, "modules", "prediction_model.py"),
    os.path.join(paths.REPO_ROOT, "modules", "recommendation_engine.py"),
    os.path.join(paths.REPO_ROOT, "modules", "correlation_analysis.py"),
)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint() -> dict[str, Any]:
    """Identify the inputs that determine the fitted models."""
    inputs = {
        os.path.basename(path): _sha256(path)
        for path in (paths.TIMESERIES_PATH, paths.SUMMARY_PATH, *_SOURCE_FILES)
        if os.path.exists(path)
    }
    return {
        "cache_version": CACHE_VERSION,
        "inputs": inputs,
        # Unpickling estimators across library versions is not supported, so a
        # version bump has to invalidate the artifact.
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }


def save(model, engine, recovery_pattern_count: int) -> str:
    """Write the fitted state of a trained model/engine pair to disk."""
    payload = {
        "fingerprint": fingerprint(),
        "model": {name: getattr(model, name) for name in _MODEL_ATTRS},
        "engine": {name: getattr(engine, name) for name in _ENGINE_ATTRS},
        "recovery_pattern_count": recovery_pattern_count,
    }
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    # Written to a sibling path first so a reader never sees a half-written file.
    tmp_path = f"{CACHE_PATH}.tmp"
    joblib.dump(payload, tmp_path, compress=3)
    os.replace(tmp_path, CACHE_PATH)
    return CACHE_PATH


def load() -> Optional[dict[str, Any]]:
    """Return the cached payload, or ``None`` when it is absent or stale."""
    if not os.path.isfile(CACHE_PATH):
        return None
    try:
        payload = joblib.load(CACHE_PATH)
    except Exception as exc:  # corrupt file, truncated download, version skew
        log.warning("Ignoring unreadable model cache at %s (%s).", CACHE_PATH, exc)
        return None

    cached = payload.get("fingerprint")
    current = fingerprint()
    if cached != current:
        log.info(
            "Model cache is stale (inputs or library versions changed) — training instead."
        )
        return None
    return payload


def apply(payload: dict[str, Any], model, engine) -> int:
    """Restore fitted state onto freshly constructed instances."""
    for name, value in payload["model"].items():
        setattr(model, name, value)
    for name, value in payload["engine"].items():
        setattr(engine, name, value)
    return int(payload["recovery_pattern_count"])
