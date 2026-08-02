"""Retrieval tool wrappers."""

from __future__ import annotations

from app.memory_store import hybrid_retrieve_with_metrics
from app.lore_store import retrieve_character_context
from app.feedback import FeedbackEvent, default_feedback_store
from app.guardrails.prompt_injection import has_suspicious_retrieved_context
from app.tools.base import ToolInput, ToolResult


class RetrieveMemoryTool:
    name = "retrieve_memory"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        query = str(tool_input.args.get("query", ""))
        k = int(tool_input.args.get("k", 5))
        context = tool_input.context
        content, metrics = await hybrid_retrieve_with_metrics(context.user_id, context.character_id, query, k=k)
        await _record_prompt_injection_observation(tool_input, content)
        return ToolResult(ok=True, content=content or "", metadata={"retrieval": metrics.to_dict()})


class RetrieveCharacterContextTool:
    name = "retrieve_character_context"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        query = str(tool_input.args.get("query", ""))
        content = await retrieve_character_context(tool_input.context.character_id, query)
        await _record_prompt_injection_observation(tool_input, content)
        return ToolResult(ok=True, content=content or "")


async def _record_prompt_injection_observation(tool_input: ToolInput, content: str | None) -> None:
    context = tool_input.context
    if not context.turn_id or not has_suspicious_retrieved_context(content):
        return
    await default_feedback_store.record_event(
        FeedbackEvent(
            event_type="prompt_injection_observed",
            user_id=context.user_id,
            session_id=context.session_id,
            turn_id=context.turn_id,
            payload={
                "tool_name": tool_input.name,
                "agent_id": context.agent_id,
            },
        )
    )
