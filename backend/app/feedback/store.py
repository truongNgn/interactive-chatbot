"""JSONL feedback store with lightweight redaction."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT
from app.feedback.events import FeedbackEvent
from app.feedback.ratings import RatingRequest

FEEDBACK_DIR = BACKEND_ROOT / "data" / "feedback"
EVENTS_PATH = FEEDBACK_DIR / "events.jsonl"
RATINGS_PATH = FEEDBACK_DIR / "ratings.jsonl"

_SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\+?\d[\d\s().-]{7,}\d"),
]


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


class FeedbackStore:
    def __init__(self, events_path: Path = EVENTS_PATH, ratings_path: Path = RATINGS_PATH) -> None:
        self._events_path = events_path
        self._ratings_path = ratings_path

    async def record_event(self, event: FeedbackEvent) -> None:
        await asyncio.to_thread(self._append_jsonl, self._events_path, event.model_dump())

    async def record_rating(self, rating: RatingRequest) -> None:
        event = FeedbackEvent(
            event_type="user_rating_submitted",
            user_id=rating.user_id,
            session_id=rating.session_id,
            turn_id=rating.turn_id,
            payload=rating.model_dump(),
        )
        await asyncio.to_thread(self._append_jsonl, self._ratings_path, rating.model_dump())
        await self.record_event(event)

    async def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._read_session_events, session_id)

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        safe_payload = _redact_value(payload)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(safe_payload, ensure_ascii=False) + "\n")

    def _read_session_events(self, session_id: str) -> list[dict[str, Any]]:
        if not self._events_path.exists():
            return []
        events: list[dict[str, Any]] = []
        with self._events_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get("session_id") == session_id:
                    events.append(item)
        return events


default_feedback_store = FeedbackStore()
