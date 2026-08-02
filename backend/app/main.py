"""FastAPI app setup and route registration."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.character_registry import character_registry
from app.config import settings
from app.feedback import RatingRequest, default_feedback_store
from app.gateway.websocket import websocket_chat as gateway_websocket_chat
from app.llm_handler import get_llm_handler
from app.stt_handler import BaseSTTHandler, get_stt_handler, validate_audio_upload
from app.tts_handler import BaseTTSHandler, get_tts_handler
from app.warmup import start_background_warmup, warmup_state

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
SUPPORTED_VOICE_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── TTS handler setup ─────────────────────────────────────────────────────
    # Heavy LLM/XTTS warm-up runs in the background by default so FastAPI can
    # accept WebSocket connections immediately after the process starts.
    tts = get_tts_handler()
    if tts.is_active:
        if settings.elevenlabs_api_key:
            logger.info("TTS: ElevenLabs ready (voice=%s).", settings.elevenlabs_voice_id)
        else:
            logger.info("TTS: Coqui XTTS-v2 configured; background warmup will preload it.")
    else:
        logger.warning("TTS: Running in text-only mode.")

    stt = get_stt_handler()
    if stt.is_active:
        logger.info("STT: %s ready.", settings.stt_provider)
    else:
        logger.info("STT: disabled.")

    app.state.tts_handler = tts
    app.state.stt_handler = stt
    warmup_task = start_background_warmup(tts, stt)
    if warmup_task and settings.warmup_blocking:
        logger.info("Warmup: blocking startup until warmup completes...")
        await warmup_task
    try:
        yield
    finally:
        if warmup_task and not warmup_task.done():
            warmup_task.cancel()
            try:
                await warmup_task
            except asyncio.CancelledError:
                logger.info("Warmup: cancelled during shutdown.")


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
        "warmup": warmup_state.to_dict(),
        "tts": {
            "provider": (
                "elevenlabs" if settings.elevenlabs_api_key
                else "xtts" if settings.xtts_speaker_wav
                else "none"
            ),
            "ready": tts.is_active,
        },
        "stt": {
            "provider": settings.stt_provider if settings.stt_enabled else "none",
            "ready": app.state.stt_handler.is_active,
            "language": settings.stt_language or None,
        },
    }


@app.get("/api/voices")
async def get_voices():
    voices_dir = BACKEND_ROOT / "voices"
    if not voices_dir.exists():
        return {"voices": []}
    voices = sorted(
        f.name for f in voices_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_VOICE_SUFFIXES
    )
    return {"voices": voices}


@app.get("/api/characters")
async def get_characters():
    return {"characters": character_registry.list_public(), "default": settings.default_character_id}


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


@app.get("/api/stt/status")
async def get_stt_status():
    stt: BaseSTTHandler = app.state.stt_handler
    return {
        "enabled": stt.is_active,
        "provider": settings.stt_provider if stt.is_active else "none",
        "language": settings.stt_language or None,
        "max_file_mb": settings.stt_max_file_mb,
        "max_duration_seconds": settings.stt_max_duration_seconds,
    }


@app.post("/api/stt")
async def transcribe_audio(
    audio: UploadFile = File(...),
    mime_type: str = Form(""),
):
    stt: BaseSTTHandler = app.state.stt_handler
    if not stt.is_active:
        raise HTTPException(status_code=503, detail="STT is not enabled.")

    resolved_mime_type = mime_type or audio.content_type or ""
    audio_bytes = await audio.read()
    try:
        validate_audio_upload(audio_bytes, resolved_mime_type)
        result = await stt.transcribe(audio_bytes, resolved_mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("STT transcription failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result.model_dump()


@app.post("/api/feedback/rating")
async def submit_feedback_rating(rating: RatingRequest):
    await default_feedback_store.record_rating(rating)
    return {"ok": True}


@app.get("/api/feedback/session/{session_id}")
async def get_feedback_session(session_id: str):
    return {"events": await default_feedback_store.get_session_events(session_id)}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await gateway_websocket_chat(websocket)
