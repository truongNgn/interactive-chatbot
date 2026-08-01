"""Minimal agent registry for Stage 3."""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._default_agent_id: str | None = None

    def register(self, agent: BaseAgent, *, default: bool = False) -> None:
        self._agents[agent.id] = agent
        if default or self._default_agent_id is None:
            self._default_agent_id = agent.id
        logger.info("Agent registered: %s default=%s", agent.id, default)

    def get(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def select(self, character_id: str | None = None) -> BaseAgent:
        if not self._default_agent_id:
            raise RuntimeError("No default agent registered.")
        agent = self._agents[self._default_agent_id]
        logger.debug("Agent selected: %s character=%s", agent.id, character_id)
        return agent

    def list_ids(self) -> list[str]:
        return sorted(self._agents)


default_agent_registry = AgentRegistry()
