"""Feedback rating schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RatingRequest(BaseModel):
    user_id: str
    session_id: str
    turn_id: str
    rating: str = Field(pattern="^(up|down)$")
    message_id: str | None = None
    reason: str | None = None
