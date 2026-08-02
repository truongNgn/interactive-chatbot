"""Trace metric helpers for Stage 6 observability."""

from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(event.get("event_type", "unknown") for event in events)
    ratings = [
        event.get("payload", {}).get("rating")
        for event in events
        if event.get("event_type") == "user_rating_submitted"
    ]
    rating_counts = Counter(rating for rating in ratings if rating)
    tool_events = [event for event in events if event.get("event_type") in {"tool_called", "tool_failed"}]
    tool_failures = [event for event in tool_events if event.get("event_type") == "tool_failed"]
    guardrail_blocks = [event for event in events if event.get("event_type") == "guardrail_blocked"]

    turn_completed = [
        event.get("payload", {})
        for event in events
        if event.get("event_type") == "turn_completed"
    ]
    latencies = [payload.get("latency_ms") for payload in turn_completed if payload.get("latency_ms") is not None]

    return {
        "event_counts": dict(counts),
        "tool_error_rate": len(tool_failures) / len(tool_events) if tool_events else 0.0,
        "guardrail_block_rate": len(guardrail_blocks) / len(events) if events else 0.0,
        "rating_up_count": rating_counts.get("up", 0),
        "rating_down_count": rating_counts.get("down", 0),
        "avg_turn_latency_ms": int(sum(latencies) / len(latencies)) if latencies else None,
    }
