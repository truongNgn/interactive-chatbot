"""
Compatibility sentence producer.

This preserves the original Orchestrator.run() API used by older code while
delegating sentence-boundary behavior to app.orchestrator.streaming.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from app.config import settings
from app.llm_handler import BaseLLMHandler, get_llm_handler
from app.models import SentenceChunk
from app.orchestrator.routing import HeuristicRouter, build_routing_context
from app.orchestrator.streaming import flush_buffer, should_flush

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, llm_handler: BaseLLMHandler | None = None) -> None:
        self._llm = llm_handler or get_llm_handler()
        self._interrupted = False

    def interrupt(self) -> None:
        """Called when the gateway receives WebSocket event 'interrupt'."""
        self._interrupted = True
        logger.info("Orchestrator interrupted")

    def reset(self) -> None:
        self._interrupted = False

    async def run(
        self,
        user_text: str,
        session_id: str,
        user_id: str,
        sentence_queue: asyncio.Queue[SentenceChunk | None],
        voice: str | None = None,
        router_enabled: bool = True,
        character_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        """Run LangGraph -> sentence buffering -> queue."""
        self.reset()
        buffer = ""
        first_chunk = True

        try:
            from app.lc_graph import graph

            resolved_character_id = character_id or settings.default_character_id

            selected_model: str | None = None
            if router_enabled:
                if settings.llm_provider.lower().strip() == "vllm":
                    large_model = settings.vllm_large_model
                    small_model = settings.vllm_small_model
                else:
                    large_model = settings.ollama_large_model
                    small_model = settings.ollama_small_model
                router = HeuristicRouter(
                    large_model=large_model,
                    small_model=small_model,
                )
                decision = router.select_model(build_routing_context(user_text))
                selected_model = decision.model

            token_queue = asyncio.Queue()

            graph_task = asyncio.create_task(
                graph.ainvoke(
                    {
                        "user_id": user_id,
                        "session_id": session_id,
                        "character_id": resolved_character_id,
                        "user_text": user_text,
                        "selected_model": selected_model,
                        "token_queue": token_queue,
                    },
                    config={
                        "run_name": "interactive_chatbot_turn",
                        "tags": ["websocket", "langgraph", "streaming"],
                        "metadata": {
                            "turn_id": turn_id,
                            "session_id": session_id,
                            "user_id": user_id,
                            "character_id": resolved_character_id,
                            "selected_model": selected_model,
                            "router_enabled": router_enabled,
                        },
                    },
                )
            )

            while True:
                if self._interrupted:
                    logger.info("Stream interrupted, stopping token consumption")
                    break

                token = await token_queue.get()
                if token is None:
                    break

                buffer += token

                if buffer and should_flush(buffer, buffer[-1], is_first_chunk=first_chunk):
                    chunk = flush_buffer(buffer, voice)
                    if chunk:
                        logger.debug(
                            "Flushed chunk [first=%s turn=%s]: emotion=%s len=%d text=%r voice=%s",
                            first_chunk,
                            turn_id,
                            chunk.emotion,
                            len(chunk.text),
                            chunk.text[:60],
                            chunk.voice,
                        )
                        await sentence_queue.put(chunk)
                        first_chunk = False
                    buffer = ""

            if buffer.strip() and not self._interrupted:
                chunk = flush_buffer(buffer, voice)
                if chunk:
                    logger.debug(
                        "Final flush [turn=%s]: emotion=%s text=%r voice=%s",
                        turn_id,
                        chunk.emotion,
                        chunk.text[:60],
                        chunk.voice,
                    )
                    await sentence_queue.put(chunk)

            if not self._interrupted:
                await graph_task

        except Exception as exc:
            logger.error("Orchestrator error [turn=%s]: %s", turn_id, exc)
            raise
        finally:
            await sentence_queue.put(None)


async def sentence_stream(
    user_text: str,
    sentence_queue: asyncio.Queue[SentenceChunk | None],
) -> AsyncGenerator[SentenceChunk, None]:
    orchestrator = Orchestrator()
    producer_task = asyncio.create_task(
        orchestrator.run(
            user_text,
            "default_session",
            "default_user",
            sentence_queue,
        )
    )
    while True:
        item = await sentence_queue.get()
        if item is None:
            break
        yield item
    await producer_task
