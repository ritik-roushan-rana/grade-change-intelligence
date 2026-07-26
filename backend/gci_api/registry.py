"""Process-wide singletons for data, models, and the feedback log.

The Streamlit app paid a ~26 second cold start on every fresh cache: read ~50K
samples, run the correlation suite, train two models, build the KNN recovery
library. Here that work happens exactly once, during FastAPI startup, so every
request is served from warm objects.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import pandas as pd

from . import paths  # noqa: F401  (puts the repo root on sys.path)
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

        log.info("Training prediction models ...")
        self.model = PredictionModel(paths.TIMESERIES_PATH, paths.SUMMARY_PATH)
        self.evaluation = self.model.train()

        log.info("Building recovery library ...")
        self.engine = RecommendationEngine(paths.TIMESERIES_PATH, paths.SUMMARY_PATH)
        self.recovery_pattern_count = self.engine.build_recovery_library()

        self.feedback_logger = FeedbackLogger(paths.FEEDBACK_LOG_PATH)

        self.startup_seconds = round(time.perf_counter() - started, 2)
        self.ready = True
        log.info("Ready in %.2fs", self.startup_seconds)


registry = Registry()
