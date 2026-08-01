"""Retrieval tool wrappers."""

from __future__ import annotations

from app.memory_store import hybrid_retrieve
from app.lore_store import retrieve_character_context
from app.tools.base import ToolInput, ToolResult


class RetrieveMemoryTool:
    name = "retrieve_memory"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        query = str(tool_input.args.get("query", ""))
        k = int(tool_input.args.get("k", 5))
        context = tool_input.context
        content = await hybrid_retrieve(context.user_id, context.character_id, query, k=k)
        return ToolResult(ok=True, content=content or "")


class RetrieveCharacterContextTool:
    name = "retrieve_character_context"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        query = str(tool_input.args.get("query", ""))
        content = await retrieve_character_context(tool_input.context.character_id, query)
        return ToolResult(ok=True, content=content or "")
