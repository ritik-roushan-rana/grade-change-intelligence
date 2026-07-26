"""HTTP surface. Thin: validate, delegate to services, serialize."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import services
from .registry import registry
from .schemas import FeedbackRequest
from .serialization import jsonable

router = APIRouter(prefix="/api")


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/health")
def health():
    return {
        "status": "ready" if registry.ready else "loading",
        "events": len(services.event_ids()) if registry.ready else 0,
        "startup_seconds": registry.startup_seconds,
    }


@router.get("/model-info")
def model_info():
    return jsonable(services.model_info())


@router.get("/events")
def get_events():
    """All grade-change events with their headline outcome metrics."""
    return jsonable(
        {
            "events": services.list_events(),
            "grades": sorted({e["grade"] for e in services.list_events()}),
            "off_spec_threshold_pct": services.OFF_SPEC_THRESHOLD,
        }
    )


@router.get("/events/{event_id}")
def get_event(event_id: int):
    try:
        return jsonable(
            {
                **services.event_summary(event_id),
                "max_time_sec": services.max_transition_time(event_id),
            }
        )
    except services.EventNotFound as exc:
        raise _not_found(exc)


@router.get("/events/{event_id}/timeline")
def get_timeline(event_id: int):
    """Full timeseries for one event."""
    try:
        return jsonable(services.timeline(event_id))
    except services.EventNotFound as exc:
        raise _not_found(exc)


@router.get("/events/{event_id}/predict")
def get_prediction(event_id: int, t: int = Query(0, ge=0, description="Seconds since transition start.")):
    """Risk level, current/projected deviation, status label and explanation."""
    try:
        payload = dict(services.predict(event_id, t))
    except services.EventNotFound as exc:
        raise _not_found(exc)
    # The raw model input row is internal; the UI reads process values from the
    # timeline endpoint instead.
    payload.pop("current_state", None)
    return jsonable(payload)


@router.get("/events/{event_id}/projection")
def get_projection(event_id: int, t: int = Query(0, ge=0)):
    """Forward trend extrapolation for the future-state charts."""
    try:
        return jsonable(services.projection(event_id, t))
    except services.EventNotFound as exc:
        raise _not_found(exc)


@router.get("/events/{event_id}/recommendations")
def get_recommendations(event_id: int, t: int = Query(0, ge=0)):
    """Recommended setpoint changes with rationale, source and limit checks."""
    try:
        return jsonable(services.recommendations(event_id, t))
    except services.EventNotFound as exc:
        raise _not_found(exc)


@router.get("/correlations")
def get_correlations():
    """Discovered correlation findings plus model feature importances."""
    return jsonable(services.correlations())


@router.get("/recipe-limits/{grade}")
def get_recipe_limits(
    grade: str,
    event_id: Optional[int] = Query(None, description="Annotate with this event's live values."),
    t: Optional[int] = Query(None, ge=0),
):
    """Min/max operating ranges for a grade."""
    try:
        return jsonable(services.recipe_limits(grade, event_id, t))
    except (services.GradeNotFound, services.EventNotFound) as exc:
        raise _not_found(exc)


@router.get("/optimal-setpoints/{grade}")
def get_optimal_setpoints(grade: str):
    """Setpoints taken from the fastest historical transitions into a grade."""
    try:
        return jsonable(services.optimal_setpoints(grade))
    except services.GradeNotFound as exc:
        raise _not_found(exc)


@router.post("/feedback", status_code=201)
def post_feedback(payload: FeedbackRequest):
    """Record an accept/reject decision against the shared feedback log."""
    try:
        result = services.log_feedback(
            payload.event_id,
            payload.timestamp,
            payload.recommendation_id,
            payload.decision,
            payload.user_notes,
        )
    except services.EventNotFound as exc:
        raise _not_found(exc)

    if not result["logged"]:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No recommendation '{payload.recommendation_id}' exists for event "
                f"#{payload.event_id} at t={payload.timestamp}s."
            ),
        )
    return jsonable(result)


@router.get("/feedback")
def get_feedback():
    """Feedback history with accept/reject totals."""
    return jsonable(services.feedback_history())
