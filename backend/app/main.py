"""
FastAPI Orchestrator — Stage 1 + Stage 2: AI Core & TTS Streaming
WebSocket /ws/chat: nhận text → LLM stream → sentence buffer → TTS → AudioChunkPayload
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm_handler import get_llm_handler
from app.models import AudioChunkPayload, DonePayload, ErrorPayload, VisemeEntry
from app.orchestrator import Orchestrator
from app.rhubarb_handler import get_visemes
from app.tts_handler import BaseTTSHandler, audio_to_base64, get_tts_handler

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


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


@app.get("/api/voices")
async def get_voices():
    voices_dir = BACKEND_ROOT / "voices"
    if not voices_dir.exists():
        return {"voices": []}
    voices = sorted(
        f.name for f in voices_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".wav"
    )
    return {"voices": voices}


@app.get("/api/models")
async def get_models():
    models_dir = PROJECT_ROOT / "frontend" / "public" / "models"
    if not models_dir.exists():
        return {"models": []}
    models = sorted(
        f.name for f in models_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".glb"
    )
    return {"models": models}


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

    async def _run_pipeline(user_text: str, session_id: str, user_id: str, tts_enabled: bool = True, voice: str | None = None, router_enabled: bool = True) -> None:
        """
        3-stage pipelined pipeline để giảm latency:

          Stage 1 (producer):     Orchestrator → sentence_queue
          Stage 2 (tts_producer): sentence_queue → TTS.synthesize() [eager, non-blocking] → tts_queue
          Stage 3 (consumer):     tts_queue → Rhubarb → WebSocket send

        Khi tts_enabled=False: bỏ qua TTS + Rhubarb, gửi text-only AudioChunkPayload ngay.
        """
        sentence_queue: asyncio.Queue = asyncio.Queue()
        tts_queue: asyncio.Queue = asyncio.Queue()

        # Stage 1: LLM → sentence_queue
        producer = asyncio.create_task(
            orchestrator.run(user_text, session_id, user_id, sentence_queue, voice, router_enabled)
        )

        async def _tts_producer() -> None:
            while True:
                chunk = await sentence_queue.get()
                if chunk is None:
                    await tts_queue.put(None)
                    return
                if tts_enabled:
                    tts_task = asyncio.create_task(_synthesize_safe(chunk))
                else:
                    # Text-only: wrap empty bytes trong completed task
                    tts_task = asyncio.create_task(_empty_audio())
                await tts_queue.put((chunk, tts_task))

        async def _synthesize_safe(chunk) -> bytes:
            try:
                return await tts.synthesize(chunk)
            except Exception as exc:
                logger.error("TTS error for chunk %r: %s", chunk.text[:40], exc)
                return b""

        async def _empty_audio() -> bytes:
            return b""

        tts_producer = asyncio.create_task(_tts_producer())

        try:
            # Stage 3: await TTS result, rồi Rhubarb → send
            while True:
                item = await tts_queue.get()
                if item is None:
                    break

                chunk, tts_task = item
                audio_bytes = await tts_task

                if tts_enabled and audio_bytes:
                    viseme_dicts = await get_visemes(audio_bytes)
                    visemes = [VisemeEntry(**v) for v in viseme_dicts]
                    duration_ms = int(visemes[-1].end * 1000) if visemes else 0
                    audio_b64 = audio_to_base64(audio_bytes)
                else:
                    visemes = []
                    duration_ms = 0
                    audio_b64 = ""

                payload = AudioChunkPayload(
                    text=chunk.text,
                    emotion=chunk.emotion,
                    audio_base64=audio_b64,
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
                if provider not in ("ollama", "deepseek", "qwen"):
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
                user_id: str = data.get("user_id", "default_user")
                session_id: str = data.get("session_id", "default_session")
                tts_enabled: bool = bool(data.get("tts_enabled", True))
                # router_enabled: frontend toggle overrides server default per-request
                router_enabled: bool = bool(data.get("router_enabled", settings.router_enabled))
                voice: str | None = data.get("voice", None)
                if not user_text:
                    await websocket.send_text(
                        ErrorPayload(message="Empty message").model_dump_json()
                    )
                    continue

                await _cancel_current()
                logger.info(
                    "New message from %s [session=%s, tts=%s, router=%s, voice=%s]: %r",
                    client, session_id, tts_enabled, router_enabled, voice, user_text[:80],
                )
                current_task = asyncio.create_task(
                    _run_pipeline(user_text, session_id, user_id, tts_enabled, voice, router_enabled)
                )

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
