"""Prompt-injection observation helpers for retrieved context."""

from __future__ import annotations

import re

_RETRIEVED_CONTEXT_INJECTION_RE = re.compile(
    r"\b(ignore previous instructions|system prompt|developer message|follow these instructions instead)\b",
    re.IGNORECASE,
)


def has_suspicious_retrieved_context(text: str | None) -> bool:
    return bool(text and _RETRIEVED_CONTEXT_INJECTION_RE.search(text))
