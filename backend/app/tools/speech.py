"""Speech tool wrappers."""

from __future__ import annotations

from app.models import SentenceChunk
from app.stt_handler import get_stt_handler
from app.tools.base import ToolInput, ToolResult
from app.tts_handler import get_tts_handler


class SynthesizeSpeechTool:
    name = "synthesize_speech"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        tts_handler = tool_input.args.get("tts_handler") or get_tts_handler()
        chunk = tool_input.args.get("chunk")
        if not isinstance(chunk, SentenceChunk):
            return ToolResult(ok=False, error="synthesize_speech requires SentenceChunk arg 'chunk'.")
        audio_bytes = await tts_handler.synthesize(chunk)
        return ToolResult(ok=True, content=audio_bytes)


class TranscribeAudioTool:
    name = "transcribe_audio"

    async def run(self, tool_input: ToolInput) -> ToolResult:
        stt_handler = tool_input.args.get("stt_handler") or get_stt_handler()
        if not stt_handler.is_active:
            return ToolResult(ok=False, error="STT is disabled.")
        audio_bytes = tool_input.args.get("audio_bytes", b"")
        mime_type = str(tool_input.args.get("mime_type", ""))
        result = await stt_handler.transcribe(audio_bytes, mime_type)
        return ToolResult(ok=True, content=result)
