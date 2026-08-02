"""Minimal guardrail pipeline for Stage 4."""

from __future__ import annotations

from typing import Any

from app.gateway.schemas import ChatRequest
from app.guardrails.input import check_input
from app.guardrails.output import check_output
from app.guardrails.tool_policy import check_tool_call


class GuardrailDecision:
    def __init__(
        self,
        allowed: bool,
        reason: str | None = None,
        redacted_text: str | None = None,
        mode: str = "block",
    ) -> None:
        self.allowed = allowed
        self.reason = reason
        self.redacted_text = redacted_text
        self.mode = mode

    def to_dict(self) -> dict[str, str | bool | None]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "redacted_text": self.redacted_text,
            "mode": self.mode,
        }


class GuardrailPipeline:
    async def check_input(self, request: ChatRequest) -> GuardrailDecision:
        return check_input(request)

    async def check_tool_call(self, tool_input: Any) -> GuardrailDecision:
        return check_tool_call(tool_input)

    async def check_output(self, text: str) -> GuardrailDecision:
        return check_output(text)
