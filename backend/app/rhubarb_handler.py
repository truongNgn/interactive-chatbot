"""
Rhubarb Lip-Sync Handler — Stage 4

Calls the Rhubarb binary on a temp WAV file, returns viseme cue list.
Falls back gracefully (returns []) if Rhubarb is not installed/configured.

Rhubarb JSON output:
  { "mouthCues": [{"start": 0.0, "end": 0.1, "value": "A"}, ...] }

Windows note: Rhubarb does not write to stdout when running under asyncio PIPE.
Solution: use -o <json_file> and read the file afterward.
"""

import asyncio
import json
import logging
import os
import tempfile

from app.config import settings
from app.tts_handler import ensure_wav

logger = logging.getLogger(__name__)


async def get_visemes(audio_bytes: bytes) -> list[dict]:
    """
    Run Rhubarb on audio_bytes.
    Returns list of {"start": float, "end": float, "value": str} dicts.
    Returns [] if Rhubarb is not configured, audio is empty, or any error.
    """
    if not audio_bytes or not settings.rhubarb_path:
        return []

    # Rhubarb only supports WAV — convert PCM/MP3 if needed
    wav_bytes = ensure_wav(audio_bytes)

    tmp_audio: str | None = None
    tmp_json: str | None = None
    try:
        # Write audio to temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_audio = f.name

        # Temp file for JSON output (-o flag — avoids asyncio stdout pipe issue on Windows)
        tmp_json_f = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_json = tmp_json_f.name
        tmp_json_f.close()

        proc = await asyncio.create_subprocess_exec(
            settings.rhubarb_path,
            "--recognizer", "phonetic",
            "-f", "json",
            "-q",
            "-o", tmp_json,
            tmp_audio,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            logger.warning("Rhubarb timed out — skipping lip-sync for this chunk")
            return []

        if proc.returncode != 0:
            logger.warning(
                "Rhubarb exited %d: %s",
                proc.returncode,
                stderr.decode(errors="replace")[:300],
            )
            return []

        # Read JSON from output file
        with open(tmp_json, encoding="utf-8") as jf:
            data = json.load(jf)

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
        for path in (tmp_audio, tmp_json):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
