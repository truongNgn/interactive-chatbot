"""Speech-to-text handler fallback.

The full STT implementation is unavailable in this checkout. This module keeps
the REST API importable and returns a disabled handler unless a production STT
adapter is restored later.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.config import settings
from app.models import TranscribeResult

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
}


class BaseSTTHandler(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> TranscribeResult:
        ...

    async def warmup(self) -> None:
        """Pre-load STT resources. Override in concrete implementations."""

    @property
    def is_active(self) -> bool:
        return True


class DisabledSTTHandler(BaseSTTHandler):
    @property
    def is_active(self) -> bool:
        return False

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> TranscribeResult:
        raise RuntimeError("STT is disabled.")


def validate_audio_upload(audio_bytes: bytes, mime_type: str) -> None:
    if not audio_bytes:
        raise ValueError("Audio upload is empty.")

    max_bytes = settings.stt_max_file_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise ValueError(f"Audio upload exceeds {settings.stt_max_file_mb} MB.")

    normalized = (mime_type or "").split(";")[0].strip().lower()
    if normalized and normalized not in SUPPORTED_AUDIO_MIME_TYPES:
        raise ValueError(f"Unsupported audio MIME type: {mime_type}")


def get_stt_handler() -> BaseSTTHandler:
    if settings.stt_enabled:
        logger.warning(
            "STT_ENABLED=true but no concrete STT implementation is present; STT remains disabled."
        )
    return DisabledSTTHandler()
