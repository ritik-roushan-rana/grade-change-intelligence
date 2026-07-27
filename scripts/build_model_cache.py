#!/usr/bin/env python3
"""Train the models once and store the fitted objects for fast startup.

Run during the container build (see the Dockerfile) or locally:

    python3 scripts/build_model_cache.py

Writes ``artifacts/model_cache.joblib``, which the API loads at startup instead
of retraining. The artifact is keyed to the datasets, the model source files and
the installed library versions; if any of those change the API ignores it and
trains normally, so a forgotten rebuild degrades speed, never correctness.
"""

from __future__ import annotations

import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO_ROOT, os.path.join(REPO_ROOT, "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from gci_api import model_cache, paths  # noqa: E402
from modules.prediction_model import PredictionModel  # noqa: E402
from modules.recommendation_engine import RecommendationEngine  # noqa: E402


def main() -> int:
    if not paths.data_files_present():
        print(
            "Process data not found. Expected both CSVs in data/.\n"
            "Regenerate with: python3 scripts/generate_grade_change_data.py",
            file=sys.stderr,
        )
        return 1

    started = time.perf_counter()

    print("Training prediction models ...", flush=True)
    model = PredictionModel(paths.TIMESERIES_PATH, paths.SUMMARY_PATH)
    evaluation = model.train()

    print("Building recovery library ...", flush=True)
    engine = RecommendationEngine(paths.TIMESERIES_PATH, paths.SUMMARY_PATH)
    pattern_count = engine.build_recovery_library()

    cache_path = model_cache.save(model, engine, pattern_count)
    elapsed = time.perf_counter() - started
    size_mb = os.path.getsize(cache_path) / 1_048_576

    # Printing the held-out scores makes the build log show that the cached
    # artifact is the validated model, not a silently different one.
    classification = (evaluation or {}).get("classification", {})
    print(
        f"Cached {pattern_count} recovery patterns and both fitted models "
        f"in {elapsed:.1f}s -> {cache_path} ({size_mb:.1f} MB)"
    )
    if classification:
        print(
            "Held-out check: "
            + ", ".join(
                f"{key}={value:.3f}"
                for key, value in classification.items()
                if isinstance(value, (int, float))
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
