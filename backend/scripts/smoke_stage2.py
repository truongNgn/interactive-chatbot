"""Smoke checks for Stage 2 gateway/orchestrator separation.

Usage:
    python scripts/smoke_stage2.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.gateway.schemas import ChatRequest, parse_client_message
from app.main import app
from app.models import Emotion, SentenceChunk
from app.orchestrator.streaming import _parse_emotion, should_flush
from app.orchestrator.turn_orchestrator import TurnOrchestrator
from app.tts_handler import BaseTTSHandler


class FakeSentenceProducer:
    def __init__(self) -> None:
        self.interrupted = False

    def interrupt(self) -> None:
        self.interrupted = True

    def reset(self) -> None:
        self.interrupted = False

    async def run(
        self,
        user_text: str,
        session_id: str,
        user_id: str,
        sentence_queue,
        voice: str | None = None,
        router_enabled: bool = True,
        character_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        await sentence_queue.put(SentenceChunk(text="Hello there.", emotion=Emotion.joy, voice=voice))
        await sentence_queue.put(None)


class FakeTTSHandler(BaseTTSHandler):
    @property
    def is_active(self) -> bool:
        return False

    async def synthesize(self, chunk: SentenceChunk) -> bytes:
        return b""


class ListSink:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.messages.append(json.loads(text))


def smoke_gateway_parse() -> None:
    parsed = parse_client_message({
        "type": "user_message",
        "text": "  hi  ",
        "user_id": "u1",
        "session_id": "s1",
        "tts_enabled": False,
        "router_enabled": False,
    })
    assert parsed.request is not None
    assert parsed.request.text == "hi"
    assert parsed.request.user_id == "u1"
    assert parsed.request.session_id == "s1"
    assert parsed.request.tts_enabled is False
    assert parsed.request.router_enabled is False
    assert parsed.request.turn_id

    invalid = parse_client_message({"type": "set_model", "provider": "bad"})
    assert invalid.error == "Unknown provider: bad"
    print("gateway_parse: ok")


def smoke_streaming_helpers() -> None:
    emotion, text = _parse_emotion("[joy] Hello!")
    assert emotion == Emotion.joy
    assert text == "Hello!"
    assert should_flush("Hello!", "!", is_first_chunk=True)
    assert not should_flush("short,", ",", is_first_chunk=False)
    print("streaming_helpers: ok")


async def smoke_turn_orchestrator() -> None:
    sink = ListSink()
    request = ChatRequest(
        text="hello",
        user_id="u1",
        session_id="s1",
        character_id="luna",
        tts_enabled=False,
        router_enabled=False,
        voice=None,
        turn_id="turn-smoke",
    )
    orchestrator = TurnOrchestrator(FakeTTSHandler(), FakeSentenceProducer())  # type: ignore[arg-type]
    await orchestrator.run_turn(request, sink)
    assert sink.messages[0]["type"] == "audio_chunk"
    assert sink.messages[0]["text"] == "Hello there."
    assert sink.messages[0]["audio_base64"] == ""
    assert sink.messages[-1]["type"] == "done"
    print("turn_orchestrator_text_only: ok")


def smoke_websocket_control_messages() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"

            websocket.send_text(json.dumps({"type": "set_model", "provider": "qwen"}))
            changed = websocket.receive_json()
            assert changed == {"type": "model_changed", "provider": "qwen"}

            websocket.send_text(json.dumps({"type": "interrupt"}))
            cleared = websocket.receive_json()
            assert cleared == {"type": "clear_queue"}
    print("websocket_control_messages: ok")


async def main() -> None:
    smoke_gateway_parse()
    smoke_streaming_helpers()
    await smoke_turn_orchestrator()
    smoke_websocket_control_messages()


if __name__ == "__main__":
    asyncio.run(main())
