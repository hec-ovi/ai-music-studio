"""SSE progress event models for album generation streaming."""

from typing import Annotated, Literal
from pydantic import BaseModel, Field


class ProgressEvent(BaseModel):
    """A single server-sent event emitted during album generation."""

    event: Annotated[
        Literal[
            "planning",
            "plan_ready",
            "plan_review_required",
            "cover_generating",
            "cover_ready",
            "song_start",
            "song_progress",
            "song_ready",
            "complete",
            "error",
        ],
        Field(description="Event type"),
    ]
    message: Annotated[str, Field(description="Human-readable status message")]
    data: Annotated[dict | None, Field(default=None, description="Optional structured payload")]
    progress: Annotated[float, Field(default=0.0, ge=0.0, le=1.0, description="Overall progress 0–1")]
