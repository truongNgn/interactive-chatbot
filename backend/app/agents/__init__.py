"""Agent layer exports."""

from app.agents.base import AgentContext, BaseAgent
from app.agents.registry import AgentRegistry, default_agent_registry
from app.agents.roleplay_agent import RoleplayChatAgent

default_agent_registry.register(RoleplayChatAgent(), default=True)

__all__ = [
    "AgentContext",
    "AgentRegistry",
    "BaseAgent",
    "RoleplayChatAgent",
    "default_agent_registry",
]
