import asyncio

from app.gateway.schemas import ChatRequest
from app.guardrails import GuardrailPipeline


def _request(text: str) -> ChatRequest:
    return ChatRequest(
        text=text,
        user_id="u1",
        session_id="s1",
        character_id="luna",
        turn_id="t1",
    )


def test_input_guardrail_blocks_oversized_message() -> None:
    decision = asyncio.run(GuardrailPipeline().check_input(_request("x" * 8001)))
    assert not decision.allowed


def test_output_guardrail_strips_internal_tags() -> None:
    decision = asyncio.run(GuardrailPipeline().check_output("<system>secret</system>Hello"))
    assert decision.allowed
    assert decision.redacted_text == "secretHello"
