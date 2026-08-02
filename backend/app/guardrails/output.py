"""Output guardrails."""

from __future__ import annotations

import re

_INTERNAL_TAG_RE = re.compile(r"</?(?:system|developer|tool|internal)[^>]*>", re.IGNORECASE)


def check_output(text: str):
    from app.guardrails.base import GuardrailDecision

    cleaned = _INTERNAL_TAG_RE.sub("", text)
    if cleaned != text:
        return GuardrailDecision(True, "Removed internal tags from output.", redacted_text=cleaned, mode="transform")
    return GuardrailDecision(True, redacted_text=text)
