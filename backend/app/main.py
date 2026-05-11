"""
FastAPI Orchestrator — Stage 1 + Stage 2: AI Core & TTS Streaming
WebSocket /ws/chat: nhận text → LLM stream → sentence buffer → TTS → AudioChunkPayload
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm_handler import LLMHandler
from app.models import AudioChunkPayload, DonePayload, ErrorPayload, VisemeEntry
from app.orchestrator import Orchestrator
from app.rhubarb_handler import get_visemes
from app.tts_handler import BaseTTSHandler, audio_to_base64, get_tts_handler

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup checks
    llm = LLMHandler()
    llm_ok = await llm.health_check()
    if llm_ok:
        logger.info("LLM: Ollama '%s' is ready.", settings.ollama_model)
    else:
        logger.warning("LLM: Ollama model '%s' not ready.", settings.ollama_model)

    tts = get_tts_handler()
    if tts.is_active:
        logger.info("TTS: ElevenLabs ready (voice=%s).", settings.elevenlabs_voice_id)
    else:
        logger.warning("TTS: Running in text-only mode (no ELEVENLABS_API_KEY).")

    app.state.tts_handler = tts
    yield


app = FastAPI(
    title="Interactive Chatbot — AI Core + TTS",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    llm = LLMHandler()
    llm_ok = await llm.health_check()
    tts: BaseTTSHandler = app.state.tts_handler
    return {
        "status": "ok" if llm_ok else "degraded",
        "llm": {"model": settings.ollama_model, "ready": llm_ok},
        "tts": {
            "provider": "elevenlabs" if tts.is_active else "none",
            "voice_id": settings.elevenlabs_voice_id if tts.is_active else None,
            "ready": tts.is_active,
        },
    }


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    logger.info("WebSocket connected: %s", client)

    tts: BaseTTSHandler = websocket.app.state.tts_handler
    orchestrator = Orchestrator()
    current_task: asyncio.Task | None = None

    async def _run_pipeline(user_text: str) -> None:
        """
        Stage 1: Orchestrator → sentence_queue
        Stage 2: sentence_queue → TTS.synthesize() → AudioChunkPayload → WebSocket
        """
        sentence_queue: asyncio.Queue = asyncio.Queue()

        # Stage 1 producer runs concurrently
        producer = asyncio.create_task(
            orchestrator.run(user_text, sentence_queue)
        )

        try:
            while True:
                chunk = await sentence_queue.get()

                # Sentinel: Stage 1 finished
                if chunk is None:
                    break

                # Stage 2: synthesize audio
                try:
                    audio_bytes = await tts.synthesize(chunk)
                except Exception as exc:
                    logger.error("TTS error for chunk %r: %s", chunk.text[:40], exc)
                    audio_bytes = b""

                # Stage 4: extract visemes from audio via Rhubarb (concurrent-safe)
                viseme_dicts = await get_visemes(audio_bytes)
                visemes = [VisemeEntry(**v) for v in viseme_dicts]
                duration_ms = (
                    int(visemes[-1].end * 1000) if visemes else 0
                )

                payload = AudioChunkPayload(
                    text=chunk.text,
                    emotion=chunk.emotion,
                    audio_base64=audio_to_base64(audio_bytes),
                    duration_ms=duration_ms,
                    visemes=visemes,
                )
                await websocket.send_text(payload.model_dump_json())

            await websocket.send_text(DonePayload().model_dump_json())

        except asyncio.CancelledError:
            logger.info("Pipeline cancelled for %s", client)
            raise
        except Exception as exc:
            logger.error("Pipeline error: %s", exc)
            try:
                await websocket.send_text(ErrorPayload(message=str(exc)).model_dump_json())
            except Exception:
                pass
        finally:
            if not producer.done():
                producer.cancel()
            try:
                await producer
            except (asyncio.CancelledError, Exception):
                pass

    async def _cancel_current() -> None:
        nonlocal current_task
        if current_task and not current_task.done():
            orchestrator.interrupt()
            current_task.cancel()
            try:
                await current_task
            except (asyncio.CancelledError, Exception):
                pass
        orchestrator.reset()

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    ErrorPayload(message="Invalid JSON").model_dump_json()
                )
                continue

            msg_type = data.get("type", "")

            if msg_type == "interrupt":
                logger.info("Interrupt signal from %s", client)
                await _cancel_current()
                await websocket.send_text(json.dumps({"type": "clear_queue"}))

            elif msg_type == "user_message":
                user_text: str = data.get("text", "").strip()
                if not user_text:
                    await websocket.send_text(
                        ErrorPayload(message="Empty message").model_dump_json()
                    )
                    continue

                await _cancel_current()
                logger.info("New message from %s: %r", client, user_text[:80])
                current_task = asyncio.create_task(_run_pipeline(user_text))

            else:
                await websocket.send_text(
                    ErrorPayload(message=f"Unknown message type: {msg_type}").model_dump_json()
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", client)
        await _cancel_current()
    except Exception as exc:
        logger.error("Unexpected WebSocket error: %s", exc)
        await _cancel_current()
