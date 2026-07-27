"""Process-wide singletons for data, models, and the feedback log.

The Streamlit app paid a ~26 second cold start on every fresh cache: read ~50K
samples, run the correlation suite, train two models, build the KNN recovery
library. Here that work happens exactly once, during FastAPI startup, so every
request is served from warm objects.

Startup is faster still when a build-time artifact is present: fitting the two
estimators is ~22 of those seconds, and the fit does not depend on the request,
so ``scripts/build_model_cache.py`` runs it during the container build and this
module reloads the fitted objects instead (see :mod:`.model_cache`). Training
remains the fallback whenever the artifact is missing or no longer matches the
data, so behaviour is identical either way.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import pandas as pd

from . import model_cache, paths  # noqa: F401  (paths puts the repo root on sys.path)
from modules.correlation_analysis import CorrelationAnalyzer
from modules.prediction_model import PredictionModel
from modules.recommendation_engine import FeedbackLogger, RecommendationEngine

log = logging.getLogger("gci.registry")


class Registry:
    """Holds the loaded data/models. Populated once by :meth:`load`."""

    def __init__(self) -> None:
        self.ts_df: Optional[pd.DataFrame] = None
        self.summary_df: Optional[pd.DataFrame] = None
        self.analyzer: Optional[CorrelationAnalyzer] = None
        self.model: Optional[PredictionModel] = None
        self.engine: Optional[RecommendationEngine] = None
        self.feedback_logger: Optional[FeedbackLogger] = None
        self.evaluation: Optional[dict] = None
        self.recovery_pattern_count: int = 0
        self.startup_seconds: Optional[float] = None
        # True when the fitted models came from the build-time artifact rather
        # than from training in this process. Surfaced on /api/health so a slow
        # cold start is diagnosable from outside the container.
        self.from_cache: bool = False
        self.ready: bool = False
        # Model objects are not documented as thread-safe for concurrent
        # predict calls; uvicorn runs handlers in a threadpool, so inference is
        # serialised. Each call is single-digit milliseconds.
        self.inference_lock = threading.Lock()

    def load(self) -> None:
        if self.ready:
            return
        if not paths.data_files_present():
            raise FileNotFoundError(
                "Process data not found. Expected both CSVs in data/. "
                "Regenerate with: python3 scripts/generate_grade_change_data.py"
            )

        paths.ensure_dirs()
        started = time.perf_counter()

        log.info("Loading process data ...")
        self.ts_df = pd.read_csv(paths.TIMESERIES_PATH, parse_dates=["timestamp"])
        self.summary_df = pd.read_csv(paths.SUMMARY_PATH)

        log.info("Discovering correlations ...")
        self.analyzer = CorrelationAnalyzer(paths.TIMESERIES_PATH, paths.SUMMARY_PATH)
        self.analyzer.run_full_analysis()

        self.model = PredictionModel(paths.TIMESERIES_PATH, paths.SUMMARY_PATH)
        self.engine = RecommendationEngine(paths.TIMESERIES_PATH, paths.SUMMARY_PATH)

        cached = model_cache.load()
        if cached is not None:
            log.info("Restoring trained models from %s ...", model_cache.CACHE_PATH)
            self.recovery_pattern_count = model_cache.apply(
                cached, self.model, self.engine
            )
            self.evaluation = self.model.evaluation_results
            self.from_cache = True
        else:
            log.info("Training prediction models ...")
            self.evaluation = self.model.train()
            log.info("Building recovery library ...")
            self.recovery_pattern_count = self.engine.build_recovery_library()

        self.feedback_logger = FeedbackLogger(paths.FEEDBACK_LOG_PATH)

        self.startup_seconds = round(time.perf_counter() - started, 2)
        self.ready = True
        log.info("Ready in %.2fs", self.startup_seconds)


registry = Registry()
