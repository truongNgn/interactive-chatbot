"""Core agent contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel


class AgentContext(BaseModel):
    user_id: str
    session_id: str
    character_id: str
    agent_id: str | None = None
    provider: str | None = None
    selected_model: str | None = None
    turn_id: str | None = None


class BaseAgent(Protocol):
    id: str

    async def stream(self, context: AgentContext, user_text: str) -> AsyncIterator[str]:
        ...
