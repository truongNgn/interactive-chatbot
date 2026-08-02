from app.feedback.traces import summarize_events


def test_summarize_events_counts_rates() -> None:
    summary = summarize_events([
        {"event_type": "tool_called", "payload": {}},
        {"event_type": "tool_failed", "payload": {}},
        {"event_type": "guardrail_blocked", "payload": {}},
        {"event_type": "turn_completed", "payload": {"latency_ms": 20}},
        {"event_type": "user_rating_submitted", "payload": {"rating": "up"}},
    ])
    assert summary["tool_error_rate"] == 0.5
    assert summary["rating_up_count"] == 1
    assert summary["avg_turn_latency_ms"] == 20
