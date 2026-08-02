import asyncio

from app.agents.base import AgentContext
from app.tools.base import ToolInput, ToolResult
from app.tools.registry import ToolRegistry


class EchoTool:
    name = "echo"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(ok=True, content=tool_input.args["text"])


def test_tool_registry_runs_unscoped_tool() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    result = asyncio.run(
        registry.run(
            ToolInput(
                name="echo",
                args={"text": "ok"},
                context=AgentContext(user_id="u1", session_id="s1", character_id="luna", turn_id="t1"),
            )
        )
    )
    assert result.ok
    assert result.content == "ok"


def test_tool_registry_blocks_roleplay_disallowed_tool() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    result = asyncio.run(
        registry.run(
            ToolInput(
                name="echo",
                args={"text": "blocked"},
                context=AgentContext(
                    user_id="u1",
                    session_id="s1",
                    character_id="luna",
                    agent_id="roleplay_chat",
                    turn_id="t1",
                ),
            )
        )
    )
    assert not result.ok
    assert "not allowed" in (result.error or "")
