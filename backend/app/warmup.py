"""Non-blocking startup warmup helpers.

This module is intentionally small: it preserves the startup contract expected
by main.py and degrades gracefully when providers are disabled or unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WarmupState:
    status: str = "idle"
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


warmup_state = WarmupState()


def start_background_warmup(tts_handler: Any, stt_handler: Any) -> asyncio.Task[None] | None:
    if not settings.warmup_on_startup:
        warmup_state.status = "disabled"
        return None

    return asyncio.create_task(_run_warmup(tts_handler, stt_handler))


async def _run_warmup(tts_handler: Any, stt_handler: Any) -> None:
    warmup_state.status = "running"
    warmup_state.started_at = time.time()
    warmup_state.completed_at = None
    warmup_state.error = None

    try:
        await asyncio.wait_for(_warmup_handlers(tts_handler, stt_handler), settings.warmup_timeout_seconds)
        warmup_state.status = "complete"
    except asyncio.TimeoutError:
        warmup_state.status = "timeout"
        warmup_state.error = f"Warmup exceeded {settings.warmup_timeout_seconds} seconds."
        logger.warning("Warmup timed out after %.1fs.", settings.warmup_timeout_seconds)
    except Exception as exc:
        warmup_state.status = "failed"
        warmup_state.error = str(exc)
        logger.warning("Warmup failed (non-fatal): %s", exc)
    finally:
        warmup_state.completed_at = time.time()


async def _warmup_handlers(tts_handler: Any, stt_handler: Any) -> None:
    tasks: list[asyncio.Task[None]] = []

    if getattr(tts_handler, "is_active", False):
        tasks.append(asyncio.create_task(tts_handler.warmup()))
    if getattr(stt_handler, "is_active", False):
        tasks.append(asyncio.create_task(stt_handler.warmup()))

    if not tasks:
        logger.info("Warmup: no active providers to preload.")
        return

    await asyncio.gather(*tasks)
