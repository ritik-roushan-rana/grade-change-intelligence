"""Request models. Responses are plain JSON built in :mod:`gci_api.services`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """An operator's decision on one recommendation."""

    event_id: int = Field(..., description="Grade change event id.")
    timestamp: int = Field(
        ...,
        ge=0,
        description=(
            "Simulation time in seconds since transition start -- the process "
            "state the recommendation was generated for."
        ),
    )
    recommendation_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Id from the recommendations response. A bare variable name is also "
            "accepted."
        ),
    )
    decision: Literal["accept", "reject"]
    user_notes: str = ""
