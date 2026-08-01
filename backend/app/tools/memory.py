"""Memory persistence tool wrapper."""

from __future__ import annotations

from app.memory_middleware import schedule_persist
from app.tools.base import ToolInput, ToolResult


class PersistMemoryTool:
    name = "persist_memory"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        context = tool_input.context
        schedule_persist(
            context.user_id,
            context.session_id,
            context.character_id,
            str(tool_input.args.get("user_text", "")),
            str(tool_input.args.get("assistant_text", "")),
            str(tool_input.args.get("emotion", "neutral")),
        )
        return ToolResult(ok=True, content={"scheduled": True})
