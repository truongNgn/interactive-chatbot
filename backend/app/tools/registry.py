"""Tool registry with structured fallback results."""

from __future__ import annotations

import logging

from app.tools.base import BaseTool, ToolInput, ToolResult

logger = logging.getLogger(__name__)

AGENT_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "roleplay_chat": {
        "retrieve_memory",
        "retrieve_character_context",
        "persist_memory",
    },
}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info("Tool registered: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    async def run(self, tool_input: ToolInput) -> ToolResult:
        agent_id = tool_input.context.agent_id
        allowed = AGENT_TOOL_ALLOWLIST.get(agent_id)
        if allowed is not None and tool_input.name not in allowed:
            error = f"Tool '{tool_input.name}' is not allowed for agent '{agent_id}'."
            logger.warning(error)
            return ToolResult(ok=False, error=error)

        tool = self.get(tool_input.name)
        if not tool:
            error = f"Unknown tool: {tool_input.name}"
            logger.warning(error)
            return ToolResult(ok=False, error=error)

        try:
            result = await tool.run(tool_input)
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
            return ToolResult(ok=False, error=str(exc))

    def list_names(self) -> list[str]:
        return sorted(self._tools)
