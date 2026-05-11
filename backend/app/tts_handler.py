"""
TTS Handler — Stage 2: Text-to-Speech.

Kiến trúc:
  - BaseTTSHandler: abstract interface
  - ElevenLabsTTSHandler: cloud TTS với emotion → VoiceSettings mapping
  - CoquiXTTSHandler: local voice cloning với XTTS-v2 (chỉ cần 6-10s mẫu giọng)
  - NoOpTTSHandler: fallback khi không cấu hình TTS (trả về bytes rỗng)

Factory function `get_tts_handler()` ưu tiên: ElevenLabs → XTTS → NoOp.
"""

import asyncio
import base64
import io
import logging
from abc import ABC, abstractmethod
from functools import lru_cache

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

    async def warmup(self) -> None:
        """Pre-load model & GPU vào VRAM. Override ở subclass nếu cần."""

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
# Coqui XTTS-v2: local voice cloning
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_xtts_model(model_name: str):
    """Load XTTS model một lần duy nhất, cache lại để dùng lại."""
    try:
        import torch
        logger.info("PyTorch %s | CUDA available: %s", torch.__version__, torch.cuda.is_available())
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch chưa được cài. Chạy:\n"
            "pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121"
        ) from exc

    try:
        import torchaudio  # noqa: F401
        logger.info("torchaudio OK")
    except ImportError as exc:
        raise RuntimeError(
            "torchaudio chưa được cài. Chạy:\n"
            "pip install torchaudio --index-url https://download.pytorch.org/whl/cu121"
        ) from exc

    try:
        from TTS.api import TTS  # type: ignore[import]
        logger.info("TTS import OK")
    except Exception as exc:
        logger.error("TTS import failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Không thể import TTS: {exc}") from exc

    # Auto-accept Coqui non-commercial license (CPML) — bỏ interactive prompt
    import os
    os.environ["COQUI_TOS_AGREED"] = "1"

    logger.info("Loading XTTS model '%s' — lần đầu sẽ tải về (~2GB)...", model_name)
    use_gpu = torch.cuda.is_available()
    logger.info("XTTS using %s", "GPU" if use_gpu else "CPU")
    tts = TTS(model_name, gpu=use_gpu)
    logger.info("XTTS model loaded.")
    return tts


class CoquiXTTSHandler(BaseTTSHandler):
    """
    Voice cloning local với XTTS-v2.
    Cần file giọng mẫu WAV (6-10 giây, mono/stereo, 22050Hz+).
    Model được load LAZY — lần đầu synthesize mới load, server start bình thường.
    Chạy inference trong thread pool để không block event loop.
    """

    def __init__(self, speaker_wav: str, language: str, model_name: str) -> None:
        self._speaker_wav = speaker_wav
        self._language = language
        self._model_name = model_name
        self._tts = None          # lazy — chưa load lúc khởi tạo
        self._executor = None

    def _get_tts(self):
        """Load model lần đầu tiên khi cần, cache lại cho các lần sau."""
        if self._tts is None:
            self._tts = _load_xtts_model(self._model_name)
        return self._tts

    async def synthesize(self, chunk: SentenceChunk) -> bytes:
        loop = asyncio.get_event_loop()

        def _run() -> bytes:
            try:
                import soundfile as sf  # type: ignore[import]
            except ImportError as exc:
                raise RuntimeError("Thiếu soundfile. Chạy: pip install soundfile") from exc

            logger.debug(
                "XTTS synthesize | lang=%s | text=%r",
                self._language,
                chunk.text[:60],
            )

            wav: list[float] = self._get_tts().tts(
                text=chunk.text,
                speaker_wav=self._speaker_wav,
                language=self._language,
            )

            buf = io.BytesIO()
            sf.write(buf, wav, samplerate=24000, format="WAV")
            buf.seek(0)
            return buf.read()

        audio_bytes = await loop.run_in_executor(self._executor, _run)
        logger.debug("XTTS done | %d bytes", len(audio_bytes))
        return audio_bytes

    async def warmup(self) -> None:
        """
        Pre-load XTTS model + warm-up GPU ngay lúc server start.
        Synthesize một câu ngắn để:
          - Load model vào VRAM (tránh delay ở request đầu tiên)
          - Khởi tạo CUDA kernels
          - Cache speaker embedding từ file WAV mẫu
        """
        logger.info("XTTS: warming up model (pre-loading into GPU)...")
        dummy = SentenceChunk(text="Hello.", emotion=Emotion.neutral)
        try:
            await self.synthesize(dummy)
            logger.info("XTTS: warmup complete — model ready in VRAM.")
        except Exception as exc:
            logger.warning("XTTS warmup failed (non-fatal): %s", exc)


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

    if settings.xtts_speaker_wav:
        import os
        if not os.path.isfile(settings.xtts_speaker_wav):
            logger.error(
                "XTTS_SPEAKER_WAV '%s' không tồn tại — fallback text-only.",
                settings.xtts_speaker_wav,
            )
            return NoOpTTSHandler()
        logger.info(
            "TTS: Coqui XTTS-v2 | speaker_wav=%s | language=%s",
            settings.xtts_speaker_wav,
            settings.xtts_language,
        )
        return CoquiXTTSHandler(
            speaker_wav=settings.xtts_speaker_wav,
            language=settings.xtts_language,
            model_name=settings.xtts_model_name,
        )

    logger.warning("Không có TTS nào được cấu hình — running in text-only mode.")
    return NoOpTTSHandler()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def audio_to_base64(audio_bytes: bytes) -> str:
    return base64.b64encode(audio_bytes).decode("utf-8")
