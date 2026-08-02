"""Tool allowlist policy."""

from __future__ import annotations

from typing import Any

AGENT_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "roleplay_chat": {
        "retrieve_memory",
        "retrieve_character_context",
        "persist_memory",
    },
}


def check_tool_call(tool_input: Any):
    from app.guardrails.base import GuardrailDecision

    agent_id = tool_input.context.agent_id
    requested_user_id = tool_input.args.get("user_id")
    requested_character_id = tool_input.args.get("character_id")
    if requested_user_id and requested_user_id != tool_input.context.user_id:
        return GuardrailDecision(False, "Tool call user scope does not match context.")
    if requested_character_id and requested_character_id != tool_input.context.character_id:
        return GuardrailDecision(False, "Tool call character scope does not match context.")

    allowed = AGENT_TOOL_ALLOWLIST.get(agent_id)
    if allowed is not None and tool_input.name not in allowed:
        return GuardrailDecision(
            False,
            f"Tool '{tool_input.name}' is not allowed for agent '{agent_id}'.",
        )
    return GuardrailDecision(True)
