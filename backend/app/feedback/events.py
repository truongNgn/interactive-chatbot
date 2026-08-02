"""Feedback event schema."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class FeedbackEvent(BaseModel):
    event_type: str
    user_id: str
    session_id: str
    turn_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
