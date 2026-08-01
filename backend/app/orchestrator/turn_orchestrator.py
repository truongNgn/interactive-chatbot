"""Turn-level orchestration for WebSocket chat.

Stage 2 keeps the legacy LangGraph sentence producer intact, but moves the
per-turn lifecycle and audio pipeline out of the gateway.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from app.gateway.schemas import ChatRequest
from app.agents.base import AgentContext
from app.models import AudioChunkPayload, DonePayload, ErrorPayload, SentenceChunk, VisemeEntry
from app.orchestrator.legacy import Orchestrator
from app.tools import ToolInput, default_tool_registry
from app.tts_handler import BaseTTSHandler, audio_to_base64

logger = logging.getLogger(__name__)


class StreamingSink(Protocol):
    async def send_text(self, text: str) -> None:
        ...


class TurnOrchestrator:
    def __init__(self, tts_handler: BaseTTSHandler, sentence_producer: Orchestrator) -> None:
        self._tts = tts_handler
        self._sentence_producer = sentence_producer

    def interrupt(self) -> None:
        self._sentence_producer.interrupt()

    def reset(self) -> None:
        self._sentence_producer.reset()

    async def run_turn(self, request: ChatRequest, sink: StreamingSink) -> None:
        sentence_queue: asyncio.Queue[SentenceChunk | None] = asyncio.Queue()
        tts_queue: asyncio.Queue[tuple[SentenceChunk, asyncio.Task[bytes]] | None] = asyncio.Queue()

        producer = asyncio.create_task(
            self._sentence_producer.run(
                request.text,
                request.session_id,
                request.user_id,
                sentence_queue,
                request.voice,
                request.router_enabled,
                request.character_id,
                request.turn_id,
            )
        )
        tts_producer = asyncio.create_task(
            self._produce_tts(request, sentence_queue, tts_queue)
        )

        try:
            while True:
                item = await tts_queue.get()
                if item is None:
                    break

                chunk, tts_task = item
                audio_bytes = await tts_task
                payload = await self._build_audio_payload(request, chunk, audio_bytes)
                await sink.send_text(payload.model_dump_json())

            await sink.send_text(DonePayload().model_dump_json())

        except asyncio.CancelledError:
            logger.info("Turn pipeline cancelled [turn=%s]", request.turn_id)
            raise
        except Exception as exc:
            logger.error("Turn pipeline error [turn=%s]: %s", request.turn_id, exc)
            try:
                await sink.send_text(ErrorPayload(message=str(exc)).model_dump_json())
            except Exception:
                pass
        finally:
            tts_producer.cancel()
            try:
                await tts_producer
            except (asyncio.CancelledError, Exception):
                pass

            if not producer.done():
                producer.cancel()
            try:
                await producer
            except (asyncio.CancelledError, Exception):
                pass

    async def _produce_tts(
        self,
        request: ChatRequest,
        sentence_queue: asyncio.Queue[SentenceChunk | None],
        tts_queue: asyncio.Queue[tuple[SentenceChunk, asyncio.Task[bytes]] | None],
    ) -> None:
        while True:
            chunk = await sentence_queue.get()
            if chunk is None:
                await tts_queue.put(None)
                return

            if request.tts_enabled:
                tts_task = asyncio.create_task(self._synthesize_safe(request, chunk))
            else:
                tts_task = asyncio.create_task(_empty_audio())
            await tts_queue.put((chunk, tts_task))

    async def _synthesize_safe(self, request: ChatRequest, chunk: SentenceChunk) -> bytes:
        result = await default_tool_registry.run(
            ToolInput(
                name="synthesize_speech",
                args={"chunk": chunk, "tts_handler": self._tts},
                context=_request_context(request),
            )
        )
        if result.ok and isinstance(result.content, bytes):
            return result.content
        if result.error:
            logger.error(
                "TTS error [turn=%s] for chunk %r: %s",
                request.turn_id,
                chunk.text[:40],
                result.error,
            )
        return b""

    async def _build_audio_payload(
        self,
        request: ChatRequest,
        chunk: SentenceChunk,
        audio_bytes: bytes,
    ) -> AudioChunkPayload:
        if request.tts_enabled and audio_bytes:
            result = await default_tool_registry.run(
                ToolInput(
                    name="generate_visemes",
                    args={"audio_bytes": audio_bytes},
                    context=_request_context(request),
                )
            )
            viseme_dicts = result.content if result.ok and isinstance(result.content, list) else []
            visemes = [VisemeEntry(**v) for v in viseme_dicts]
            duration_ms = int(visemes[-1].end * 1000) if visemes else 0
            audio_b64 = audio_to_base64(audio_bytes)
        else:
            visemes = []
            duration_ms = 0
            audio_b64 = ""

        return AudioChunkPayload(
            text=chunk.text,
            emotion=chunk.emotion,
            audio_base64=audio_b64,
            duration_ms=duration_ms,
            visemes=visemes,
        )


async def _empty_audio() -> bytes:
    return b""


def _request_context(request: ChatRequest) -> AgentContext:
    return AgentContext(
        user_id=request.user_id,
        session_id=request.session_id,
        character_id=request.character_id,
        turn_id=request.turn_id,
    )
