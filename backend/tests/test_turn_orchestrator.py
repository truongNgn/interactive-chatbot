import asyncio
import json

from app.gateway.schemas import ChatRequest
from app.models import Emotion, SentenceChunk
from app.orchestrator.turn_orchestrator import TurnOrchestrator
from app.tts_handler import BaseTTSHandler


class FakeProducer:
    def interrupt(self) -> None:
        pass

    def reset(self) -> None:
        pass

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
        await sentence_queue.put(SentenceChunk(text="Hello.", emotion=Emotion.neutral))
        await sentence_queue.put(None)


class FakeTTS(BaseTTSHandler):
    @property
    def is_active(self) -> bool:
        return False

    async def synthesize(self, chunk: SentenceChunk) -> bytes:
        return b""


class Sink:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.messages.append(json.loads(text))


def test_turn_orchestrator_text_only_turn() -> None:
    async def run() -> list[dict]:
        sink = Sink()
        request = ChatRequest(
            text="hello",
            user_id="u1",
            session_id="s1",
            character_id="luna",
            tts_enabled=False,
            router_enabled=False,
            turn_id="turn-test",
        )
        orchestrator = TurnOrchestrator(FakeTTS(), FakeProducer())  # type: ignore[arg-type]
        await orchestrator.run_turn(request, sink)
        return sink.messages

    messages = asyncio.run(run())
    assert messages[0]["type"] == "audio_chunk"
    assert messages[0]["turn_id"] == "turn-test"
    assert messages[-1]["type"] == "done"
