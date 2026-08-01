"""Smoke checks for Stage 3 AgentRegistry and ToolRegistry MVP.

Usage:
    python scripts/smoke_stage3.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents import AgentContext, default_agent_registry
from app.tools import ToolInput, default_tool_registry


def smoke_agent_registry() -> None:
    agent = default_agent_registry.select("luna")
    assert agent.id == "roleplay_chat"
    assert "roleplay_chat" in default_agent_registry.list_ids()
    print("agent_registry: ok")


async def smoke_tool_registry() -> None:
    context = AgentContext(
        user_id="smoke_user",
        session_id="smoke_session",
        character_id="luna",
        agent_id="roleplay_chat",
        turn_id="turn-stage3-smoke",
    )

    lore = await default_tool_registry.run(
        ToolInput(
            name="retrieve_character_context",
            args={"query": "hello"},
            context=context,
        )
    )
    assert lore.ok
    assert isinstance(lore.content, str)

    blocked = await default_tool_registry.run(
        ToolInput(
            name="synthesize_speech",
            args={},
            context=context,
        )
    )
    assert not blocked.ok
    assert "not allowed" in (blocked.error or "")
    print("tool_registry: ok")


async def main() -> None:
    smoke_agent_registry()
    await smoke_tool_registry()


if __name__ == "__main__":
    asyncio.run(main())
