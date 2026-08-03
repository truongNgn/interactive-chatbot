"""Turn-level orchestration for WebSocket chat.

Stage 2 keeps the legacy LangGraph sentence producer intact, but moves the
per-turn lifecycle and audio pipeline out of the gateway.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Protocol

from app.gateway.schemas import ChatRequest
from app.agents.base import AgentContext
from app.conversation_store import append_message
from app.feedback import FeedbackEvent, default_feedback_store
from app.guardrails import GuardrailPipeline
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
        self._guardrails = GuardrailPipeline()

    def interrupt(self) -> None:
        self._sentence_producer.interrupt()

    def reset(self) -> None:
        self._sentence_producer.reset()

    async def run_turn(self, request: ChatRequest, sink: StreamingSink) -> None:
        started_at = time.perf_counter()
        await self._record_event(request, "turn_started", {
            "character_id": request.character_id,
            "tts_enabled": request.tts_enabled,
            "router_enabled": request.router_enabled,
        })
        await self._record_chat_message_safe(
            request,
            role="human",
            content=request.text,
            emotion=None,
        )
        first_response_ms: int | None = None
        first_audio_ms: int | None = None
        assistant_text_parts: list[str] = []
        assistant_emotion: str | None = None
        input_decision = await self._guardrails.check_input(request)
        await self._record_event(request, "input_guardrail_checked", input_decision.to_dict())
        if not input_decision.allowed:
            await self._record_event(request, "guardrail_blocked", input_decision.to_dict())
            await sink.send_text(ErrorPayload(message=input_decision.reason or "Message blocked.").model_dump_json())
            await self._record_event(request, "turn_failed", {"reason": input_decision.reason, "blocked": True})
            return

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
                if tts_queue.empty():
                    await _raise_if_failed(producer)

                item = await tts_queue.get()
                if item is None:
                    await _raise_if_failed(producer)
                    break

                chunk, tts_task = item
                audio_bytes = await tts_task
                output_decision = await self._guardrails.check_output(chunk.text)
                if output_decision.reason:
                    await self._record_event(request, "output_guardrail_checked", output_decision.to_dict())
                if output_decision.redacted_text is not None and output_decision.redacted_text != chunk.text:
                    chunk = chunk.model_copy(update={"text": output_decision.redacted_text})
                assistant_text_parts.append(chunk.text)
                assistant_emotion = chunk.emotion.value
                payload = await self._build_audio_payload(request, chunk, audio_bytes)
                if first_response_ms is None:
                    first_response_ms = int((time.perf_counter() - started_at) * 1000)
                    await self._record_event(
                        request,
                        "first_response_chunk",
                        {"latency_ms": first_response_ms},
                    )
                if first_audio_ms is None and request.tts_enabled and audio_bytes:
                    first_audio_ms = int((time.perf_counter() - started_at) * 1000)
                    await self._record_event(
                        request,
                        "first_audio",
                        {"latency_ms": first_audio_ms},
                    )
                await sink.send_text(payload.model_dump_json())

            await sink.send_text(DonePayload().model_dump_json())
            if assistant_text_parts:
                await self._record_chat_message_safe(
                    request,
                    role="ai",
                    content=" ".join(part.strip() for part in assistant_text_parts if part.strip()),
                    emotion=assistant_emotion,
                )
            await self._record_event(
                request,
                "turn_completed",
                {
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "time_to_first_response_ms": first_response_ms,
                    "time_to_first_audio_ms": first_audio_ms,
                },
            )

        except asyncio.CancelledError:
            logger.info("Turn pipeline cancelled [turn=%s]", request.turn_id)
            await self._record_event(request, "turn_failed", {"reason": "cancelled"})
            raise
        except Exception as exc:
            logger.error("Turn pipeline error [turn=%s]: %s", request.turn_id, exc)
            await self._record_event(request, "turn_failed", {"reason": str(exc)})
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
            turn_id=request.turn_id,
        )

    async def _record_event(self, request: ChatRequest, event_type: str, payload: dict) -> None:
        await default_feedback_store.record_event(
            FeedbackEvent(
                event_type=event_type,
                user_id=request.user_id,
                session_id=request.session_id,
                turn_id=request.turn_id,
                payload=payload,
            )
        )

    async def _record_chat_message_safe(
        self,
        request: ChatRequest,
        *,
        role: str,
        content: str,
        emotion: str | None,
    ) -> None:
        try:
            await append_message(
                user_id=request.user_id,
                conversation_id=request.session_id,
                character_id=request.character_id,
                role=role,  # type: ignore[arg-type]
                content=content,
                turn_id=request.turn_id,
                emotion=emotion,
            )
        except Exception as exc:
            logger.warning(
                "Postgres conversation persistence failed [turn=%s role=%s]: %s",
                request.turn_id,
                role,
                exc,
            )


async def _empty_audio() -> bytes:
    return b""


async def _raise_if_failed(task: asyncio.Task) -> None:
    if not task.done() or task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        raise exc


def _request_context(request: ChatRequest) -> AgentContext:
    return AgentContext(
        user_id=request.user_id,
        session_id=request.session_id,
        character_id=request.character_id,
        turn_id=request.turn_id,
    )
