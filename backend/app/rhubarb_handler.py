"""
Rhubarb Lip-Sync Handler — Stage 4

Calls the Rhubarb binary on a temp MP3 file, returns viseme cue list.
Falls back gracefully (returns []) if Rhubarb is not installed/configured.

Rhubarb JSON output:
  { "mouthCues": [{"start": 0.0, "end": 0.1, "value": "A"}, ...] }
"""

import asyncio
import json
import logging
import os
import tempfile

from app.config import settings

logger = logging.getLogger(__name__)


async def get_visemes(audio_bytes: bytes) -> list[dict]:
    """
    Run Rhubarb on audio_bytes (MP3/WAV).
    Returns list of {"start": float, "end": float, "value": str} dicts.
    Returns [] if Rhubarb is not configured, audio is empty, or any error.
    """
    if not audio_bytes or not settings.rhubarb_path:
        return []

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        proc = await asyncio.create_subprocess_exec(
            settings.rhubarb_path,
            "--machineReadable",
            "--recognizer", "phonetic",
            "-f", "json",
            "-q",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            logger.warning("Rhubarb timed out — skipping lip-sync for this chunk")
            return []

        if proc.returncode != 0:
            logger.warning(
                "Rhubarb exited %d: %s",
                proc.returncode,
                stderr.decode(errors="replace")[:200],
            )
            return []

        data = json.loads(stdout.decode())
        cues: list[dict] = data.get("mouthCues", [])
        logger.debug("Rhubarb: %d viseme cues", len(cues))
        return cues

    except FileNotFoundError:
        logger.warning(
            "Rhubarb binary not found at '%s' — lip-sync disabled.", settings.rhubarb_path
        )
        return []
    except Exception as exc:
        logger.error("Rhubarb error: %s", exc)
        return []
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
