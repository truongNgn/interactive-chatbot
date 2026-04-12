"""
TTS Handler — Stage 2: Text-to-Speech với ElevenLabs.

Kiến trúc:
  - BaseTTSHandler: abstract interface
  - ElevenLabsTTSHandler: cloud TTS với emotion → VoiceSettings mapping
  - NoOpTTSHandler: fallback khi không có API key (trả về bytes rỗng, client hiển thị text)

Factory function `get_tts_handler()` tự động chọn handler dựa trên config.
"""

import base64
import logging
from abc import ABC, abstractmethod

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs

from app.config import settings
from app.models import Emotion, SentenceChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Emotion → VoiceSettings mapping
# Tham số: stability (0-1, cao = ít biến tấu), similarity_boost (0-1),
#          style (0-1, cao = phóng đại biểu cảm), use_speaker_boost
# ---------------------------------------------------------------------------
_EMOTION_VOICE_SETTINGS: dict[Emotion, VoiceSettings] = {
    Emotion.joy: VoiceSettings(
        stability=0.30,
        similarity_boost=0.75,
        style=0.55,
        use_speaker_boost=True,
    ),
    Emotion.sad: VoiceSettings(
        stability=0.85,
        similarity_boost=0.70,
        style=0.10,
        use_speaker_boost=False,
    ),
    Emotion.neutral: VoiceSettings(
        stability=0.50,
        similarity_boost=0.75,
        style=0.00,
        use_speaker_boost=True,
    ),
    Emotion.thinking: VoiceSettings(
        stability=0.70,
        similarity_boost=0.70,
        style=0.10,
        use_speaker_boost=False,
    ),
    Emotion.surprise: VoiceSettings(
        stability=0.20,
        similarity_boost=0.80,
        style=0.70,
        use_speaker_boost=True,
    ),
    Emotion.anger: VoiceSettings(
        stability=0.30,
        similarity_boost=0.90,
        style=0.80,
        use_speaker_boost=True,
    ),
}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseTTSHandler(ABC):
    @abstractmethod
    async def synthesize(self, chunk: SentenceChunk) -> bytes:
        """Chuyển SentenceChunk → audio bytes. Trả về b'' nếu không có audio."""

    @property
    def is_active(self) -> bool:
        """True nếu handler có thể sinh audio thật."""
        return True


# ---------------------------------------------------------------------------
# ElevenLabs implementation
# ---------------------------------------------------------------------------

class ElevenLabsTTSHandler(BaseTTSHandler):
    def __init__(self) -> None:
        self._client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self._voice_id = settings.elevenlabs_voice_id
        self._model_id = settings.elevenlabs_model_id
        self._output_format = settings.elevenlabs_output_format

    async def synthesize(self, chunk: SentenceChunk) -> bytes:
        """
        Gọi ElevenLabs convert() để stream audio bytes về, gom lại thành
        một buffer hoàn chỉnh cho câu hiện tại.
        Latency thực tế: ~200-400ms cho câu ngắn với eleven_turbo_v2_5.
        """
        voice_settings = _EMOTION_VOICE_SETTINGS.get(chunk.emotion, _EMOTION_VOICE_SETTINGS[Emotion.neutral])

        logger.debug(
            "TTS synthesize | emotion=%s stability=%.2f style=%.2f | text=%r",
            chunk.emotion,
            voice_settings.stability,
            voice_settings.style or 0.0,
            chunk.text[:60],
        )

        audio_buf = bytearray()
        try:
            async for audio_chunk in self._client.text_to_speech.convert(
                voice_id=self._voice_id,
                text=chunk.text,
                model_id=self._model_id,
                output_format=self._output_format,  # type: ignore[arg-type]
                voice_settings=voice_settings,
            ):
                audio_buf.extend(audio_chunk)

            logger.debug("TTS done | %d bytes for %r", len(audio_buf), chunk.text[:40])
            return bytes(audio_buf)

        except Exception as exc:
            logger.error("ElevenLabs TTS error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Fallback: no-op (TTS không cấu hình)
# ---------------------------------------------------------------------------

class NoOpTTSHandler(BaseTTSHandler):
    """
    Trả về bytes rỗng. Frontend sẽ nhận AudioChunkPayload với audio_base64=""
    và fallback về hiển thị text thay vì phát audio.
    """

    @property
    def is_active(self) -> bool:
        return False

    async def synthesize(self, chunk: SentenceChunk) -> bytes:
        logger.debug("NoOpTTS: no audio for %r", chunk.text[:40])
        return b""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_tts_handler() -> BaseTTSHandler:
    if settings.elevenlabs_api_key:
        logger.info("TTS: ElevenLabs (voice=%s, model=%s)", settings.elevenlabs_voice_id, settings.elevenlabs_model_id)
        return ElevenLabsTTSHandler()

    logger.warning("ELEVENLABS_API_KEY not set — running in text-only mode (NoOpTTSHandler).")
    return NoOpTTSHandler()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def audio_to_base64(audio_bytes: bytes) -> str:
    return base64.b64encode(audio_bytes).decode("utf-8")
