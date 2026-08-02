"""Input guardrails."""

from __future__ import annotations

import re

from app.gateway.schemas import ChatRequest

MAX_INPUT_CHARS = 8000
_SUSPICIOUS_INPUT_RE = re.compile(
    r"\b(ignore previous instructions|reveal system prompt|developer message|bypass guardrails)\b",
    re.IGNORECASE,
)


def check_input(request: ChatRequest):
    from app.guardrails.base import GuardrailDecision

    text = request.text.strip()
    if not text:
        return GuardrailDecision(False, "Empty message.")
    if len(text) > MAX_INPUT_CHARS:
        return GuardrailDecision(False, f"Message exceeds {MAX_INPUT_CHARS} characters.")
    if _SUSPICIOUS_INPUT_RE.search(text):
        return GuardrailDecision(
            True,
            "Suspicious instruction pattern observed.",
            mode="observe",
        )
    return GuardrailDecision(True)
