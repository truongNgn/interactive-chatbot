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
from app.llm_handler import get_llm_handler
from app.models import AudioChunkPayload, DonePayload, ErrorPayload
from app.orchestrator import Orchestrator
from app.tts_handler import BaseTTSHandler, audio_to_base64, get_tts_handler

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── LLM warmup ────────────────────────────────────────────────────────────
    # Gửi dummy request để Ollama load model vào VRAM trước request đầu tiên.
    llm = get_llm_handler()
    llm_ok = await llm.health_check()
    if llm_ok:
        logger.info("LLM: provider='%s' is ready.", settings.llm_provider)
        await llm.warmup()
    else:
        logger.warning("LLM: provider='%s' not ready — skipping warmup.", settings.llm_provider)

    # ── TTS warmup ────────────────────────────────────────────────────────────
    # Pre-load XTTS vào GPU ngay khi server start (không lazy nữa).
    tts = get_tts_handler()
    if tts.is_active:
        if settings.elevenlabs_api_key:
            logger.info("TTS: ElevenLabs ready (voice=%s).", settings.elevenlabs_voice_id)
        else:
            logger.info("TTS: Coqui XTTS-v2 — starting warmup...")
            await tts.warmup()
    else:
        logger.warning("TTS: Running in text-only mode.")

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
    llm = get_llm_handler()
    llm_ok = await llm.health_check()
    tts: BaseTTSHandler = app.state.tts_handler
    return {
        "status": "ok" if llm_ok else "degraded",
        "llm": {"provider": settings.llm_provider, "ready": llm_ok},
        "tts": {
            "provider": (
                "elevenlabs" if settings.elevenlabs_api_key
                else "xtts" if settings.xtts_speaker_wav
                else "none"
            ),
            "ready": tts.is_active,
        },
    }


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    logger.info("WebSocket connected: %s", client)

    tts: BaseTTSHandler = websocket.app.state.tts_handler
    current_provider: str = settings.llm_provider
    orchestrator = Orchestrator(get_llm_handler(current_provider))
    current_task: asyncio.Task | None = None

    # Thông báo provider hiện tại cho client ngay khi connect
    await websocket.send_text(json.dumps({"type": "connected", "provider": current_provider}))

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

                # Stage 2: synthesize audio (async, non-blocking)
                try:
                    audio_bytes = await tts.synthesize(chunk)
                except Exception as exc:
                    logger.error("TTS error for chunk %r: %s", chunk.text[:40], exc)
                    # Graceful fallback: gửi audio rỗng, client hiển thị text
                    audio_bytes = b""

                payload = AudioChunkPayload(
                    text=chunk.text,
                    emotion=chunk.emotion,
                    audio_base64=audio_to_base64(audio_bytes),
                    # duration_ms và visemes sẽ được điền ở Stage 4 (Rhubarb)
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

            elif msg_type == "set_model":
                provider = data.get("provider", "ollama").lower()
                if provider not in ("ollama", "deepseek"):
                    await websocket.send_text(
                        ErrorPayload(message=f"Unknown provider: {provider}").model_dump_json()
                    )
                    continue
                await _cancel_current()
                current_provider = provider
                orchestrator = Orchestrator(get_llm_handler(current_provider))
                logger.info("LLM provider switched to '%s' for %s", current_provider, client)
                await websocket.send_text(json.dumps({"type": "model_changed", "provider": current_provider}))

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
