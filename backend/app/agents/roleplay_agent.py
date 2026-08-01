"""Roleplay chat agent wrapping the existing LangGraph pipeline."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from app.agents.base import AgentContext

logger = logging.getLogger(__name__)


class RoleplayChatAgent:
    id = "roleplay_chat"

    async def stream(self, context: AgentContext, user_text: str) -> AsyncIterator[str]:
        from app.lc_graph import graph

        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        graph_task = asyncio.create_task(
            graph.ainvoke(
                {
                    "user_id": context.user_id,
                    "session_id": context.session_id,
                    "character_id": context.character_id,
                    "user_text": user_text,
                    "selected_model": context.selected_model,
                    "token_queue": token_queue,
                    "turn_id": context.turn_id,
                    "agent_id": self.id,
                },
                config={
                    "run_name": "interactive_chatbot_turn",
                    "tags": ["websocket", "langgraph", "streaming", f"agent:{self.id}"],
                    "metadata": {
                        "turn_id": context.turn_id,
                        "session_id": context.session_id,
                        "user_id": context.user_id,
                        "character_id": context.character_id,
                        "selected_model": context.selected_model,
                        "agent_id": self.id,
                    },
                },
            )
        )

        try:
            while True:
                token = await token_queue.get()
                if token is None:
                    break
                yield token
            await graph_task
        except Exception:
            if not graph_task.done():
                graph_task.cancel()
            raise
