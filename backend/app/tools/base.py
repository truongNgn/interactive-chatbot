"""Core tool contracts."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from app.agents.base import AgentContext


class ToolInput(BaseModel):
    name: str
    args: dict[str, Any]
    context: AgentContext


class ToolResult(BaseModel):
    ok: bool
    content: Any = None
    error: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class BaseTool(Protocol):
    name: str

    async def run(self, tool_input: ToolInput) -> ToolResult:
        ...
