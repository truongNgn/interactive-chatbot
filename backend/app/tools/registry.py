"""Tool registry with structured fallback results."""

from __future__ import annotations

import logging

from app.feedback import FeedbackEvent, default_feedback_store
from app.guardrails.base import GuardrailPipeline
from app.tools.base import BaseTool, ToolInput, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._guardrails = GuardrailPipeline()

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info("Tool registered: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    async def run(self, tool_input: ToolInput) -> ToolResult:
        decision = await self._guardrails.check_tool_call(tool_input)
        if not decision.allowed:
            error = decision.reason or f"Tool call blocked: {tool_input.name}"
            logger.warning(error)
            await self._record_tool_event("tool_failed", tool_input, {"error": error, "blocked": True})
            return ToolResult(ok=False, error=error)

        tool = self.get(tool_input.name)
        if not tool:
            error = f"Unknown tool: {tool_input.name}"
            logger.warning(error)
            await self._record_tool_event("tool_failed", tool_input, {"error": error})
            return ToolResult(ok=False, error=error)

        try:
            result = await tool.run(tool_input)
            await self._record_tool_event(
                "tool_called" if result.ok else "tool_failed",
                tool_input,
                {"ok": result.ok, "error": result.error, "metadata": result.metadata},
            )
            logger.debug(
                "Tool called: %s ok=%s turn=%s agent_context=%s",
                tool_input.name,
                result.ok,
                tool_input.context.turn_id,
                tool_input.context.character_id,
            )
            return result
        except Exception as exc:
            logger.warning("Tool failed: %s turn=%s error=%s", tool_input.name, tool_input.context.turn_id, exc)
            await self._record_tool_event("tool_failed", tool_input, {"error": str(exc)})
            return ToolResult(ok=False, error=str(exc))

    def list_names(self) -> list[str]:
        return sorted(self._tools)

    async def _record_tool_event(self, event_type: str, tool_input: ToolInput, payload: dict) -> None:
        context = tool_input.context
        if not context.turn_id:
            return
        await default_feedback_store.record_event(
            FeedbackEvent(
                event_type=event_type,
                user_id=context.user_id,
                session_id=context.session_id,
                turn_id=context.turn_id,
                payload={
                    "tool_name": tool_input.name,
                    "agent_id": context.agent_id,
                    **payload,
                },
            )
        )
