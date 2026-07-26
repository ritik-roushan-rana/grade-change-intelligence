"""Read paths into the loaded models.

Every function here mirrors, step for step, what the Streamlit dashboard did
inline. The rules that decide *what* is shown (window sizes, thresholds,
projection maths, status wording) are reproduced exactly; the models themselves
are called, never re-implemented.
"""

from __future__ import annotations

import functools
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import paths  # noqa: F401  (puts the repo root on sys.path)
from modules.recipe_limits import (
    RECIPE_LIMITS,
    check_within_limits,
    get_limits_for_grade,
)

from .explanations import (
    FEATURE_IMPORTANCE_SOURCE,
    PROJECTION_CAVEAT,
    RECIPE_LIMITS_SOURCE,
    explain_feature,
)
from .registry import registry

# Off-spec specification limit, in percent deviation. Mirrors
# PredictionModel.RISK_THRESHOLD, which owns the value for scoring.
OFF_SPEC_THRESHOLD = 2.5

# Sampling interval of the historical data, in seconds.
SAMPLE_INTERVAL_SEC = 15

# Window sizes copied from the Streamlit page so predictions match 1:1.
HISTORY_WINDOW_SAMPLES = 9  # last ~2 min fed to predict_risk
PROJECTION_FIT_SAMPLES = 8  # trailing samples the trend line is fitted to
PROJECTION_MIN_SAMPLES = 5  # below this the dashboard showed "insufficient data"
PROJECTION_HORIZON_SEC = 300  # forward extrapolation span

# Variable -> unit, for axis labels and value formatting in the UI.
VARIABLE_UNITS = {
    "stock_flow": "units",
    "filler_flow": "units",
    "steam_pressure": "kPa",
    "machine_speed": "m/min",
    "moisture_pct": "%",
    "ash_pct": "%",
    "caliper_um": "\u00b5m",
    "basis_weight_gsm": "gsm",
}


class EventNotFound(Exception):
    """Raised when a requested grade-change event id is not in the dataset."""


class GradeNotFound(Exception):
    """Raised when a grade has no recipe-limit entry."""


# ── Data access ────────────────────────────────────────────────────────────────


def event_ids() -> List[int]:
    return sorted(int(x) for x in registry.summary_df["grade_change_event_id"].unique())


def _require_event(event_id: int) -> pd.Series:
    rows = registry.summary_df[registry.summary_df["grade_change_event_id"] == event_id]
    if rows.empty:
        raise EventNotFound(f"Grade change event #{event_id} does not exist.")
    return rows.iloc[0]


def event_summary(event_id: int) -> Dict[str, Any]:
    row = _require_event(event_id)
    return {
        "event_id": int(row["grade_change_event_id"]),
        "grade": row["grade"],
        "max_deviation_pct": float(row["max_deviation_pct"]),
        "went_off_spec": bool(row["went_off_spec"]),
        "n_operator_actions": int(row["n_operator_actions"]),
        "time_to_stabilize_sec": int(row["time_to_stabilize_sec"]),
    }


def list_events() -> List[Dict[str, Any]]:
    return [event_summary(eid) for eid in event_ids()]


@functools.lru_cache(maxsize=256)
def _transition_frame(event_id: int) -> pd.DataFrame:
    """Transition-phase samples for one event, ordered by elapsed time."""
    _require_event(event_id)
    event_data = registry.ts_df[registry.ts_df["grade_change_event_id"] == event_id]
    return (
        event_data[event_data["phase"] == "transition"]
        .sort_values("time_since_transition_start_sec")
        .reset_index(drop=True)
        .copy()
    )


def transition_frame(event_id: int) -> pd.DataFrame:
    return _transition_frame(event_id)


def max_transition_time(event_id: int) -> int:
    frame = transition_frame(event_id)
    if frame.empty:
        return 0
    return int(frame["time_since_transition_start_sec"].max())


def timeline(event_id: int) -> Dict[str, Any]:
    """Full timeseries for one event, both phases, plus operator actions."""
    _require_event(event_id)
    event_data = registry.ts_df[
        registry.ts_df["grade_change_event_id"] == event_id
    ].sort_values(["phase", "time_since_transition_start_sec"])

    samples = (
        event_data.sort_values("timestamp")
        .to_dict("records")
    )
    transition = transition_frame(event_id)
    actions = transition[transition["operator_action"].fillna("") != ""]

    return {
        "event": event_summary(event_id),
        "max_time_sec": max_transition_time(event_id),
        "sample_interval_sec": SAMPLE_INTERVAL_SEC,
        "off_spec_threshold_pct": OFF_SPEC_THRESHOLD,
        "samples": samples,
        "operator_actions": [
            {
                "time_since_transition_start_sec": int(
                    row["time_since_transition_start_sec"]
                ),
                "operator_action": row["operator_action"],
                "basis_weight_deviation_pct": float(row["basis_weight_deviation_pct"]),
            }
            for _, row in actions.iterrows()
        ],
    }


def _state_at(event_id: int, t: int) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """Resolve simulation time ``t`` to (elapsed samples, current state, history).

    Same slicing the dashboard used: everything up to and including ``t`` is
    "what the operator has seen", the last row is the live state, and the
    trailing 9 samples are the history window handed to the model.
    """
    transition = transition_frame(event_id)
    if transition.empty:
        raise EventNotFound(f"Event #{event_id} has no transition-phase data.")

    elapsed = transition[transition["time_since_transition_start_sec"] <= t]
    if elapsed.empty:
        return elapsed, {}, elapsed

    current_state = elapsed.iloc[-1].to_dict()
    history_window = elapsed.tail(HISTORY_WINDOW_SAMPLES)
    return elapsed, current_state, history_window


# ── Prediction ────────────────────────────────────────────────────────────────


@functools.lru_cache(maxsize=4096)
def _predict_cached(event_id: int, t: int) -> Dict[str, Any]:
    elapsed, current_state, history = _state_at(event_id, t)
    if not current_state:
        return {
            "available": False,
            "message": "Move the slider forward to see predictions.",
            "event_id": event_id,
            "t_sec": t,
        }

    with registry.inference_lock:
        prediction = registry.model.predict_risk(current_state, history)

    current_dev = prediction["current_deviation_pct"]

    # Deviation change across the visible history window. The dashboard used
    # this (not the model's per-step rate) to decide the status wording.
    window_dev_change = 0.0
    if len(history) >= 2:
        window_dev_change = float(
            history["basis_weight_deviation_pct"].iloc[-1]
            - history["basis_weight_deviation_pct"].iloc[0]
        )

    status = _status_label(current_dev, window_dev_change, prediction.get("time_to_breach_sec"))

    factors = [
        {
            "variable": f["variable"],
            "label": _titleize(f["variable"]),
            "importance": f["importance"],
            "current_value": f["current_value"],
        }
        for f in prediction.get("contributing_factors", [])
    ]

    return {
        "available": True,
        "event_id": event_id,
        "t_sec": t,
        "max_time_sec": max_transition_time(event_id),
        "samples_elapsed": int(len(elapsed)),
        "grade": current_state.get("grade"),
        "off_spec_threshold_pct": OFF_SPEC_THRESHOLD,
        "risk_level": prediction["risk_level"],
        "risk_probability": prediction["risk_probability"],
        "current_deviation_pct": current_dev,
        "deviation_vs_spec_pct": round(current_dev - OFF_SPEC_THRESHOLD, 2),
        "projected_deviation_pct": prediction["projected_deviation_pct"],
        "time_to_breach_sec": prediction.get("time_to_breach_sec"),
        "window_deviation_change_pct": round(window_dev_change, 3),
        "status": status,
        "explanation": prediction["explanation"],
        "source": prediction["source"],
        "contributing_factors": factors,
        "current_state": current_state,
    }


def _status_label(
    current_dev: float, window_dev_change: float, time_to_breach: Optional[int]
) -> Dict[str, Any]:
    """The fourth metric card on the Live Monitor.

    Kept as its own step because the wording deliberately avoids contradicting
    the risk level: a transition can be above the 2.5% limit *and* recovering.
    """
    if current_dev > OFF_SPEC_THRESHOLD:
        if window_dev_change < -0.05:
            return {
                "kind": "recovering",
                "label": "Status",
                "value": "Recovering \u2193",
                "detail": "Trending on-spec",
                "tone": "good",
            }
        return {
            "kind": "off_spec",
            "label": "Status",
            "value": "Off-Spec \u26a0",
            "detail": f"Above {OFF_SPEC_THRESHOLD}%",
            "tone": "bad",
        }
    if time_to_breach is not None and time_to_breach > 0:
        return {
            "kind": "time_to_breach",
            "label": "Time to Breach",
            "value": f"{time_to_breach}s",
            "detail": None,
            "tone": "warn",
        }
    return {
        "kind": "within_spec",
        "label": "Status",
        "value": "Within Spec \u2713",
        "detail": None,
        "tone": "good",
    }


def predict(event_id: int, t: int) -> Dict[str, Any]:
    _require_event(event_id)
    return _predict_cached(event_id, _clamp_time(event_id, t))


def _clamp_time(event_id: int, t: int) -> int:
    """Keep the cache keyed on in-range integers."""
    return max(0, min(int(t), max_transition_time(event_id)))


# ── Future-state projection ───────────────────────────────────────────────────


def projection(event_id: int, t: int) -> Dict[str, Any]:
    """Trend extrapolation for the future-state charts.

    Port of the Streamlit projection block: fit a first-order polynomial to the
    trailing 8 samples of deviation, moisture and steam pressure, then evaluate
    it forward in 15-second steps. Deviation is floored at zero (a negative
    deviation percentage is not physically meaningful here). Per-60s rates are
    the fitted slope times four steps.
    """
    _require_event(event_id)
    t = _clamp_time(event_id, t)
    elapsed, current_state, _ = _state_at(event_id, t)

    base = {
        "event_id": event_id,
        "t_sec": t,
        "off_spec_threshold_pct": OFF_SPEC_THRESHOLD,
        "horizon_sec": PROJECTION_HORIZON_SEC,
        "caveat": PROJECTION_CAVEAT,
    }

    if len(elapsed) < PROJECTION_MIN_SAMPLES:
        return {
            **base,
            "available": False,
            "message": "Insufficient data points for trend projection. Move the slider forward.",
            "actual": [],
            "projected": [],
            "rates": None,
        }

    recent = elapsed.tail(PROJECTION_FIT_SAMPLES)
    recent_t = recent["time_since_transition_start_sec"].values.astype(float)

    if len(recent_t) < 2 or recent_t.std() == 0:
        return {
            **base,
            "available": False,
            "message": "Insufficient data points for trend projection. Move the slider forward.",
            "actual": [],
            "projected": [],
            "rates": None,
        }

    max_time = max_transition_time(event_id)
    future_t = np.arange(
        t + SAMPLE_INTERVAL_SEC,
        min(t + PROJECTION_HORIZON_SEC, max_time + PROJECTION_HORIZON_SEC),
        SAMPLE_INTERVAL_SEC,
    )

    dev_coeffs = np.polyfit(recent_t, recent["basis_weight_deviation_pct"].values, 1)
    projected_dev = np.clip(np.polyval(dev_coeffs, future_t), 0, None)

    moist_coeffs = np.polyfit(recent_t, recent["moisture_pct"].values, 1)
    projected_moist = np.polyval(moist_coeffs, future_t)

    steam_coeffs = np.polyfit(recent_t, recent["steam_pressure"].values, 1)
    projected_steam = np.polyval(steam_coeffs, future_t)

    actual = [
        {
            "t": int(row["time_since_transition_start_sec"]),
            "deviation_pct": float(row["basis_weight_deviation_pct"]),
            "moisture_pct": float(row["moisture_pct"]),
            "steam_pressure": float(row["steam_pressure"]),
        }
        for _, row in elapsed.iterrows()
    ]

    projected = [
        {
            "t": int(ft),
            "deviation_pct": float(pd_),
            "moisture_pct": float(pm),
            "steam_pressure": float(ps),
        }
        for ft, pd_, pm, ps in zip(future_t, projected_dev, projected_moist, projected_steam)
    ]

    # Slope is per sample-second; four 15s steps make one minute.
    steps_per_minute = 4
    return {
        **base,
        "available": True,
        "message": None,
        "now": {
            "t": t,
            "deviation_pct": float(current_state["basis_weight_deviation_pct"]),
            "moisture_pct": float(current_state["moisture_pct"]),
            "steam_pressure": float(current_state["steam_pressure"]),
        },
        "actual": actual,
        "projected": projected,
        "rates": {
            "deviation_pct_per_60s": round(float(dev_coeffs[0]) * steps_per_minute, 3),
            "moisture_pct_per_60s": round(float(moist_coeffs[0]) * steps_per_minute, 4),
            "steam_kpa_per_60s": round(float(steam_coeffs[0]) * steps_per_minute, 3),
        },
    }


# ── Recommendations ───────────────────────────────────────────────────────────


def recommendation_id(event_id: int, rec: Dict[str, Any]) -> str:
    """Stable identity for one suggestion.

    Includes the exact values shown, so advancing the slider to a new process
    state yields a genuinely new suggestion that can be decided again -- the
    same identity rule the Streamlit app used.
    """
    return (
        f"{event_id}|{rec['variable']}"
        f"|{float(rec['current_value']):.2f}|{float(rec['recommended_value']):.2f}"
    )


@functools.lru_cache(maxsize=4096)
def _recommendations_cached(event_id: int, t: int) -> Dict[str, Any]:
    prediction = _predict_cached(event_id, t)
    if not prediction.get("available"):
        return {
            "available": False,
            "message": prediction.get("message"),
            "event_id": event_id,
            "t_sec": t,
            "action": None,
            "recommendations": [],
        }

    current_state = prediction["current_state"]
    with registry.inference_lock:
        result = registry.engine.recommend(current_state, _model_prediction_view(prediction))

    recs = []
    for rec in result.get("recommendations", []):
        limit_check = rec.get("recipe_limit_check", {}) or {}
        change = float(rec["change"])
        recs.append(
            {
                "id": recommendation_id(event_id, rec),
                "variable": rec["variable"],
                "label": _titleize(rec["variable"]),
                "current_value": float(rec["current_value"]),
                "recommended_value": float(rec["recommended_value"]),
                "recommended_value_original": (
                    float(rec["recommended_value_original"])
                    if rec.get("recommended_value_original") is not None
                    else None
                ),
                "change": change,
                "direction": "up" if change > 0 else "down",
                "unit": rec["unit"],
                "rationale": rec["rationale"],
                "source": rec["source"],
                # The engine calls this "confidence"; it is surfaced as
                # "Similarity Match" because it scores neighbour agreement.
                "similarity_match": float(rec["confidence"]),
                "recipe_limit": {
                    "clamped": bool(limit_check.get("flagged", False)),
                    "within_limits": limit_check.get("within_limits"),
                    "min": limit_check.get("min"),
                    "max": limit_check.get("max"),
                    "violation": limit_check.get("violation"),
                    "flag_message": limit_check.get("flag_message"),
                },
                # Risk context is carried onto each suggestion so the feedback
                # log records the risk level the decision was made under.
                "risk_level": result.get("risk_level", prediction["risk_level"]),
            }
        )

    return {
        "available": True,
        "event_id": event_id,
        "t_sec": t,
        "action": result["action"],
        "message": result["message"],
        "risk_level": result.get("risk_level", prediction["risk_level"]),
        "estimated_recovery_time_sec": result.get("estimated_recovery_time_sec"),
        "similar_events_used": result.get("similar_events_used", []),
        "source": result.get("source"),
        "recommendations": recs,
    }


def _model_prediction_view(prediction: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild the dict shape ``RecommendationEngine.recommend`` expects."""
    return {
        "risk_level": prediction["risk_level"],
        "risk_probability": prediction["risk_probability"],
        "projected_deviation_pct": prediction["projected_deviation_pct"],
        "current_deviation_pct": prediction["current_deviation_pct"],
        "time_to_breach_sec": prediction["time_to_breach_sec"],
    }


def recommendations(event_id: int, t: int) -> Dict[str, Any]:
    _require_event(event_id)
    return _recommendations_cached(event_id, _clamp_time(event_id, t))


def find_recommendation(event_id: int, t: int, rec_id: str) -> Optional[Dict[str, Any]]:
    """Look up a suggestion by id so feedback can be logged from its own values."""
    payload = recommendations(event_id, t)
    for rec in payload.get("recommendations", []):
        if rec["id"] == rec_id:
            return rec
    # Fall back to matching on the variable name: tolerates a client that sends
    # a bare variable, without letting values drift from what the model said.
    for rec in payload.get("recommendations", []):
        if rec["variable"] == rec_id:
            return rec
    return None


# ── Correlations & feature importance ─────────────────────────────────────────


def correlations() -> Dict[str, Any]:
    findings = registry.analyzer.findings
    payload = []
    for finding in findings:
        payload.append(
            {
                "id": finding["id"],
                "title": finding["title"],
                "description": finding["description"],
                "correlation_strength": finding.get("correlation_strength"),
                "p_value": finding.get("p_value"),
                "impact": finding["impact"],
                "source": finding["source"],
                "recommendation": finding["recommendation"],
                "variables_involved": finding.get("variables_involved", []),
                "detail_data": finding.get("detail_data"),
            }
        )

    importance_df = registry.model.get_feature_importances().head(12)
    top_importance = importance_df["Importance"].max() if not importance_df.empty else 1.0
    features = [
        {
            "feature": row["Feature"],
            "label": _titleize(row["Feature"]),
            "importance": float(row["Importance"]),
            "importance_pct": round(float(row["Importance"]) * 100, 1),
            # Bar length relative to the top feature, as the dashboard drew it.
            "relative_pct": round(
                min(float(row["Importance"]) / float(top_importance) * 100, 100), 1
            ),
            "explanation": explain_feature(row["Feature"]),
        }
        for _, row in importance_df.iterrows()
    ]

    return {
        "findings": payload,
        "total_findings": len(payload),
        "high_impact": sum(1 for f in payload if f["impact"] == "high"),
        "medium_impact": sum(1 for f in payload if f["impact"] == "medium"),
        "low_impact": sum(1 for f in payload if f["impact"] == "low"),
        "n_events_analyzed": int(registry.summary_df["grade_change_event_id"].nunique()),
        "feature_importances": features,
        "feature_importance_source": FEATURE_IMPORTANCE_SOURCE,
    }


# ── Recipe limits ─────────────────────────────────────────────────────────────


def recipe_limits(grade: str, event_id: Optional[int] = None, t: Optional[int] = None):
    """Operating ranges for a grade, optionally annotated with live values."""
    limits = get_limits_for_grade(grade)
    if not limits:
        raise GradeNotFound(f"No recipe limits available for grade '{grade}'.")

    current_state: Dict[str, Any] = {}
    if event_id is not None and t is not None:
        prediction = predict(event_id, t)
        if prediction.get("available"):
            current_state = prediction["current_state"]

    variables = []
    for variable, (lo, hi) in limits.items():
        entry = {
            "variable": variable,
            "label": _titleize(variable),
            "unit": VARIABLE_UNITS.get(variable, ""),
            "min": lo,
            "max": hi,
            "range_label": f"{lo} \u2013 {hi}",
            "current_value": None,
            "within_limits": None,
            "violation": None,
        }
        if current_state:
            value = current_state.get(variable, 0)
            check = check_within_limits(grade, variable, value)
            entry["current_value"] = round(float(value), 2)
            entry["within_limits"] = bool(check["within_limits"])
            entry["violation"] = check["violation"]
        variables.append(entry)

    return {
        "grade": grade,
        "variables": variables,
        "source": RECIPE_LIMITS_SOURCE,
        "annotated": bool(current_state),
    }


def grades() -> List[str]:
    return list(RECIPE_LIMITS.keys())


def optimal_setpoints(grade: str) -> Dict[str, Any]:
    if grade not in set(registry.summary_df["grade"].unique()):
        raise GradeNotFound(f"Unknown grade '{grade}'.")
    with registry.inference_lock:
        optimal = registry.engine.get_optimal_setpoints_for_grade(grade)
    return {
        "target_grade": optimal["target_grade"],
        "source_grade": optimal["source_grade"],
        "setpoints": [
            {
                "variable": key,
                "label": _titleize(key),
                "value": value,
                "unit": VARIABLE_UNITS.get(key, ""),
            }
            for key, value in optimal["optimal_setpoints"].items()
        ],
        "basis_weight_target_gsm": optimal["basis_weight_target_gsm"],
        "avg_stabilize_time_sec": optimal["avg_stabilize_time_sec"],
        "source": optimal["source"],
    }


# ── Feedback ──────────────────────────────────────────────────────────────────


def log_feedback(
    event_id: int, t: int, rec_id: str, decision: str, user_notes: str = ""
) -> Dict[str, Any]:
    rec = find_recommendation(event_id, t, rec_id)
    if rec is None:
        return {"logged": False, "reason": "recommendation_not_found"}

    # FeedbackLogger owns the CSV schema; hand it the same dict shape the
    # Streamlit app did so the log format is unchanged.
    registry.feedback_logger.log_decision(
        event_id,
        {
            "risk_level": rec["risk_level"],
            "variable": rec["variable"],
            "recommended_value": rec["recommended_value"],
            "current_value": rec["current_value"],
            "change": rec["change"],
            "source": rec["source"],
        },
        decision,
        user_notes,
    )
    return {
        "logged": True,
        "event_id": event_id,
        "t_sec": t,
        "recommendation_id": rec["id"],
        "variable": rec["variable"],
        "decision": decision,
    }


def feedback_history() -> Dict[str, Any]:
    log = registry.feedback_logger.get_log()
    stats = registry.feedback_logger.get_accuracy_stats()
    entries = [] if log.empty else log.to_dict("records")
    return {
        "entries": entries,
        "columns": list(registry.feedback_logger.COLUMNS),
        "stats": {
            "total_decisions": stats.get("total_decisions", 0),
            "accepted": stats.get("accepted", 0),
            "rejected": stats.get("rejected", 0),
            "accept_rate": stats.get("accept_rate", 0),
            "reject_rate": stats.get("reject_rate", 0),
            "by_variable": stats.get("by_variable", {}),
        },
    }


# ── Misc ──────────────────────────────────────────────────────────────────────


# The memoised lookups a cache clear is allowed to drop. Everything else in
# memory (datasets, trained models, recovery library) is warm-up state.
_CACHES: Dict[str, Any] = {
    "transition_frames": _transition_frame,
    "predictions": _predict_cached,
    "recommendations": _recommendations_cached,
}


def cache_stats() -> Dict[str, Any]:
    """Hit/miss counters for the per-(event, time) memoisation.

    Exposed so an operator can see whether the slider is being served from cache
    rather than re-scoring, and judge whether clearing it would cost anything.
    """
    caches = []
    for name, fn in _CACHES.items():
        info = fn.cache_info()
        looked_up = info.hits + info.misses
        caches.append(
            {
                "name": name,
                "label": _titleize(name),
                "entries": info.currsize,
                "capacity": info.maxsize,
                "hits": info.hits,
                "misses": info.misses,
                "hit_rate": round(info.hits / looked_up, 3) if looked_up else None,
            }
        )
    return {
        "caches": caches,
        "total_entries": sum(c["entries"] for c in caches),
        # Models are held separately and are never dropped by a cache clear:
        # retraining them would cost the full startup time again.
        "models_loaded": registry.ready,
        "model_warmup_seconds": registry.startup_seconds,
    }


def clear_caches() -> Dict[str, Any]:
    """Drop memoised scoring results.

    Only the derived per-(event, time) results are discarded. The trained models,
    the recovery library and the loaded datasets stay in memory — clearing those
    would mean paying the whole warm-up again for no benefit.
    """
    before = {name: fn.cache_info().currsize for name, fn in _CACHES.items()}
    for fn in _CACHES.values():
        fn.cache_clear()
    return {
        "cleared": before,
        "total_cleared": sum(before.values()),
        "models_retained": True,
    }


def clear_feedback_log() -> Dict[str, Any]:
    """Truncate the operator feedback log, keeping its header row.

    Destructive: the accept/reject history is the evidence used to judge
    suggestion quality, so this exists for resetting a demo rather than for
    routine use. Written through the logger's own column list so the file it
    leaves behind is exactly what FeedbackLogger expects to append to.
    """
    logger = registry.feedback_logger
    existing = logger.get_log()
    removed = 0 if existing.empty else len(existing)

    pd.DataFrame(columns=list(logger.COLUMNS)).to_csv(logger.log_path, index=False)

    return {"cleared": True, "entries_removed": removed, "path": logger.log_path}


def model_info() -> Dict[str, Any]:
    evaluation = registry.evaluation or {}
    return {
        "classifier": "Random Forest (150 trees, max depth 12, balanced classes)",
        "regressor": "Gradient Boosting (150 estimators, max depth 6)",
        "recommender": "KNN over historical recovery patterns",
        "recovery_patterns": registry.recovery_pattern_count,
        "validation": "Event-based holdout split (75/25) -- no samples shared across events",
        "evaluation": evaluation,
        "startup_seconds": registry.startup_seconds,
    }


# Word-level fixes for label generation. A naive title-case turns model feature
# names into "Bw Volatility" and "Caliper Um"; these keep acronyms upper case and
# render trailing unit tokens as units.
_LABEL_WORDS = {
    "bw": "BW",
    "pct": "(%)",
    "um": "(\u00b5m)",
    "gsm": "(gsm)",
    "sec": "(s)",
    "knn": "KNN",
}


def _titleize(name: str) -> str:
    """``steam_pressure`` -> ``Steam Pressure``, ``caliper_um`` -> ``Caliper (\u00b5m)``."""
    words = []
    for word in name.split("_"):
        lowered = word.lower()
        words.append(_LABEL_WORDS.get(lowered, word.title()))
    return " ".join(words)
