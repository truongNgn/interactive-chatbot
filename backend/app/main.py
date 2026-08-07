"""FastAPI app setup and route registration."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from app.auth import AuthContext, get_request_auth_context, issue_dev_token
from app.character_registry import character_registry
from app.config import settings
from app.conversation_store import (
    LoginRequest,
    RegisterRequest,
    authenticate_user,
    create_user,
    delete_conversation,
    get_conversation_detail,
    get_or_create_google_user,
    get_user,
    list_conversations,
    user_public_dict,
)
from app.db import db_ready, init_db
from app.feedback import RatingRequest, default_feedback_store
from app.gateway.websocket import websocket_chat as gateway_websocket_chat
from app.llm_handler import get_llm_handler
from app.rate_limit import RateLimitMiddleware
from app.session_history import session_history_ready
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
    # ── LangSmith Observability status check ──────────────────────────────────
    import os
    tracing_enabled = os.environ.get("LANGCHAIN_TRACING_V2") or os.environ.get("LANGSMITH_TRACING")
    project = os.environ.get("LANGCHAIN_PROJECT") or os.environ.get("LANGSMITH_PROJECT")
    api_key = os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("LANGSMITH_API_KEY")
    if tracing_enabled == "true":
        if api_key:
            logger.info("LangSmith Tracing is ENABLED. Project: '%s'. Traces will be sent to LangSmith.", project)
        else:
            logger.warning("LangSmith Tracing is set to true, but API KEY is missing! Traces will not be sent.")
    else:
        logger.info("LangSmith Tracing is DISABLED.")

    # ── TTS handler setup ─────────────────────────────────────────────────────
    # Heavy LLM/XTTS warm-up runs in the background by default so FastAPI can
    # accept WebSocket connections immediately after the process starts.
    tts = get_tts_handler()
    if tts.is_active:
        if tts.provider_name.startswith("elevenlabs"):
            logger.info("TTS: %s ready (voice=%s).", tts.provider_name, settings.elevenlabs_voice_id)
        elif tts.provider_name == "xtts":
            logger.info("TTS: Coqui XTTS-v2 configured; background warmup will preload it.")
        else:
            logger.info("TTS: %s ready.", tts.provider_name)
    else:
        logger.warning("TTS: Running in text-only mode.")

    stt = get_stt_handler()
    if stt.is_active:
        logger.info("STT: %s ready.", settings.stt_provider)
    else:
        logger.info("STT: disabled.")

    app.state.tts_handler = tts
    app.state.stt_handler = stt
    app.state.db_ready = False
    if settings.database_auto_create:
        app.state.db_ready = await init_db()
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


async def _llm_health() -> bool:
    """Probe the configured LLM provider without letting a misconfigured
    provider turn the health/ready probes into an opaque 500."""
    try:
        return await get_llm_handler().health_check()
    except Exception as exc:
        logger.error("LLM provider '%s' unavailable: %s", settings.llm_provider, exc)
        return False


@app.get("/health")
async def health():
    llm_ok = await _llm_health()
    tts: BaseTTSHandler = app.state.tts_handler
    return {
        "status": "ok" if llm_ok else "degraded",
        "llm": {"provider": settings.llm_provider, "ready": llm_ok},
        "warmup": warmup_state.to_dict(),
        "tts": {
            "provider": tts.provider_name,
            "ready": tts.is_active,
        },
        "stt": {
            "provider": settings.stt_provider if settings.stt_enabled else "none",
            "ready": app.state.stt_handler.is_active,
            "language": settings.stt_language or None,
        },
    }


@app.get("/ready")
async def readiness():
    llm_ok = await _llm_health()
    history_ok = session_history_ready()
    database_ok = await db_ready()
    tts: BaseTTSHandler = app.state.tts_handler
    ready = llm_ok and history_ok
    return {
        "status": "ready" if ready else "degraded",
        "app": {"ready": True},
        "llm": {"provider": settings.llm_provider, "ready": llm_ok},
        "session_history": {
            "backend": settings.session_backend,
            "ready": history_ok,
        },
        "vector_store": {
            "provider": "chroma",
            "ready": True,
            "path": settings.chroma_path,
        },
        "database": {
            "provider": "postgres",
            "configured": bool(settings.database_url),
            "ready": database_ok,
        },
        "tts": {"provider": tts.provider_name, "ready": tts.is_active},
        "warmup": warmup_state.to_dict(),
    }


@app.post("/api/auth/register")
async def register(payload: RegisterRequest):
    try:
        user = await create_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    token = issue_dev_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user_public_dict(user)}


@app.post("/api/auth/login")
async def login(payload: LoginRequest):
    user = await authenticate_user(payload)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = issue_dev_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user_public_dict(user)}


class GoogleLoginRequest(BaseModel):
    credential: str


@app.post("/api/auth/google")
async def login_google(payload: GoogleLoginRequest):
    if not settings.google_client_id:
        raise HTTPException(
            status_code=500,
            detail="Google Client ID is not configured on the backend. Please configure GOOGLE_CLIENT_ID."
        )

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests

        id_info = id_token.verify_oauth2_token(
            payload.credential,
            requests.Request(),
            settings.google_client_id
        )

        if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid issuer.")

        email = id_info.get("email")
        if not email:
            raise ValueError("Email not present in Google token.")

        display_name = id_info.get("name")
    except Exception as exc:
        logger.error("Google login failed: %s", exc)
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Google token: {exc}"
        ) from exc

    user = await get_or_create_google_user(email, display_name)
    token = issue_dev_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user_public_dict(user)}


@app.get("/api/auth/me")
async def me(auth: AuthContext = Depends(get_request_auth_context)):
    user = await get_user(auth.user_id)
    if user:
        return {"user": user_public_dict(user), "auth": {"mode": auth.mode}}
    raise HTTPException(status_code=404, detail="Authenticated user not found.")


@app.get("/api/conversations")
async def conversations(auth: AuthContext = Depends(get_request_auth_context)):
    return {"conversations": [item.model_dump() for item in await list_conversations(auth.user_id)]}


@app.get("/api/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    auth: AuthContext = Depends(get_request_auth_context),
):
    detail = await get_conversation_detail(auth.user_id, conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return detail.model_dump()


@app.delete("/api/conversations/{conversation_id}")
async def remove_conversation(
    conversation_id: str,
    auth: AuthContext = Depends(get_request_auth_context),
):
    deleted = await delete_conversation(auth.user_id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"ok": True}


@app.get("/api/voices")
async def get_voices(auth: AuthContext = Depends(get_request_auth_context)):
    voices = []

    if settings.gcs_bucket_name:
        try:
            from google.cloud import storage
            storage_client = storage.Client()
            bucket = storage_client.bucket(settings.gcs_bucket_name)
            prefix = f"voices/{auth.user_id}/"
            blobs = bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                name = blob.name.replace("voices/", "")
                if name and Path(name).suffix.lower() in SUPPORTED_VOICE_SUFFIXES:
                    voices.append(name)
        except Exception as exc:
            logger.error("Failed to list GCS voices: %s", exc)

    voices_dir = BACKEND_ROOT / "voices" / auth.user_id
    if voices_dir.exists():
        local_voices = [
            f"{auth.user_id}/{f.name}" for f in voices_dir.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_VOICE_SUFFIXES
        ]
        for name in local_voices:
            if name not in voices:
                voices.append(name)

    return {"voices": sorted(voices)}


@app.post("/api/voices/upload")
async def upload_voice(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_request_auth_context)
):
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in SUPPORTED_VOICE_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Supported: {SUPPORTED_VOICE_SUFFIXES}",
        )

    filename = Path(file.filename).name if file.filename else "voice.wav"
    user_voice_key = f"{auth.user_id}/{filename}"

    if settings.gcs_bucket_name:
        try:
            from google.cloud import storage
            storage_client = storage.Client()
            bucket = storage_client.bucket(settings.gcs_bucket_name)
            blob = bucket.blob(f"voices/{user_voice_key}")

            content = await file.read()
            blob.upload_from_string(content, content_type=file.content_type)
            logger.info("Voice uploaded to GCS for user %s: %s", auth.user_id, filename)
        except Exception as exc:
            logger.error("Failed to upload voice to GCS: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload voice to GCS: {exc}",
            ) from exc
    else:
        voices_dir = BACKEND_ROOT / "voices" / auth.user_id
        voices_dir.mkdir(parents=True, exist_ok=True)
        target_path = voices_dir / filename
        try:
            content = await file.read()
            with open(target_path, "wb") as f:
                f.write(content)
            logger.info("Voice uploaded locally for user %s: %s", auth.user_id, target_path)
        except Exception as exc:
            logger.error("Failed to save uploaded voice locally: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save voice file locally: {exc}",
            ) from exc

    return {"filename": user_voice_key}


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
async def submit_feedback_rating(
    rating: RatingRequest,
    auth: AuthContext = Depends(get_request_auth_context),
):
    await default_feedback_store.record_rating(rating.model_copy(update={"user_id": auth.user_id}))
    return {"ok": True}


@app.get("/api/feedback/session/{session_id}")
async def get_feedback_session(
    session_id: str,
    auth: AuthContext = Depends(get_request_auth_context),
):
    events = await default_feedback_store.get_session_events(session_id)
    return {"events": [event for event in events if event.get("user_id") == auth.user_id]}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await gateway_websocket_chat(websocket)
