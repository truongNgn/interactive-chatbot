"""Lip-sync tool wrapper."""

from __future__ import annotations

from app.rhubarb_handler import get_visemes
from app.tools.base import ToolInput, ToolResult


class GenerateVisemesTool:
    name = "generate_visemes"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        audio_bytes = tool_input.args.get("audio_bytes", b"")
        if not audio_bytes:
            return ToolResult(ok=True, content=[])
        visemes = await get_visemes(audio_bytes)
        return ToolResult(ok=True, content=visemes)
