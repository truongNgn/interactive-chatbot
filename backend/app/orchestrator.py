"""
Orchestrator: nhận token stream từ LLM, gom câu (sentence-buffering),
bóc tách emotion tag, yield SentenceChunk vào queue cho Stage 2.
"""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator

from app.llm_handler import LLMHandler
from app.models import Emotion, SentenceChunk

logger = logging.getLogger(__name__)

# Regex bắt emotion tag ở đầu chuỗi: [joy], [sad], v.v.
_EMOTION_TAG_RE = re.compile(
    r"^\s*\[(joy|sad|neutral|thinking|surprise|anger)\]\s*",
    re.IGNORECASE,
)

# Các ký tự kết thúc câu — bao gồm dấu câu tiếng Anh & Việt
_SENTENCE_END_RE = re.compile(r"[.!?。？！]+")

# Dấu phân cách phụ (comma, semicolon) — chỉ dùng khi câu đủ dài (≥ 40 ký tự)
_CLAUSE_END_RE = re.compile(r"[,;]+")

_MIN_CLAUSE_LEN = 40  # ký tự tối thiểu để flush theo dấu phẩy


def _parse_emotion(text: str) -> tuple[Emotion, str]:
    """
    Bóc tách emotion tag khỏi đầu chuỗi.
    Trả về (emotion, cleaned_text).
    """
    match = _EMOTION_TAG_RE.match(text)
    if match:
        emotion_str = match.group(1).lower()
        clean = text[match.end():].strip()
        try:
            return Emotion(emotion_str), clean
        except ValueError:
            pass
    return Emotion.neutral, text.strip()


def _should_flush(buffer: str, char: str) -> bool:
    """Quyết định có nên flush buffer thành câu không."""
    if _SENTENCE_END_RE.search(char):
        return True
    if _CLAUSE_END_RE.search(char) and len(buffer) >= _MIN_CLAUSE_LEN:
        return True
    return False


class Orchestrator:
    def __init__(self) -> None:
        self._llm = LLMHandler()
        self._interrupted = False

    def interrupt(self) -> None:
        """Được gọi khi nhận WebSocket event 'interrupt' từ client."""
        self._interrupted = True
        logger.info("Orchestrator interrupted")

    def reset(self) -> None:
        self._interrupted = False

    async def run(
        self,
        user_text: str,
        sentence_queue: asyncio.Queue[SentenceChunk | None],
    ) -> None:
        """
        Chạy pipeline LLM -> sentence-buffering -> queue.
        Gửi None vào queue khi xong (sentinel) hoặc khi bị interrupt.
        """
        self.reset()
        buffer = ""

        try:
            async for token in self._llm.stream_tokens(user_text):
                if self._interrupted:
                    logger.info("Stream interrupted, stopping token consumption")
                    break

                buffer += token

                # Kiểm tra từng ký tự cuối buffer xem có nên flush không
                if buffer and _should_flush(buffer, buffer[-1]):
                    chunk = _flush_buffer(buffer)
                    if chunk:
                        logger.debug("Flushed chunk: emotion=%s text=%r", chunk.emotion, chunk.text[:60])
                        await sentence_queue.put(chunk)
                    buffer = ""

            # Flush phần còn lại (câu cuối có thể không có dấu câu)
            if buffer.strip() and not self._interrupted:
                chunk = _flush_buffer(buffer)
                if chunk:
                    logger.debug("Final flush: emotion=%s text=%r", chunk.emotion, chunk.text[:60])
                    await sentence_queue.put(chunk)

        except Exception as exc:
            logger.error("Orchestrator error: %s", exc)
            raise
        finally:
            # Sentinel để báo downstream pipeline biết là xong
            await sentence_queue.put(None)


def _flush_buffer(raw: str) -> SentenceChunk | None:
    """Tạo SentenceChunk từ raw buffer, bóc tách emotion tag."""
    emotion, text = _parse_emotion(raw)
    text = text.strip()
    if not text:
        return None
    return SentenceChunk(text=text, emotion=emotion)


async def sentence_stream(
    user_text: str,
    sentence_queue: asyncio.Queue[SentenceChunk | None],
) -> AsyncGenerator[SentenceChunk, None]:
    """
    Convenience async generator: wrap Orchestrator.run() thành generator
    để các consumer có thể `async for chunk in sentence_stream(...)`.
    """
    orchestrator = Orchestrator()

    producer_task = asyncio.create_task(
        orchestrator.run(user_text, sentence_queue)
    )

    while True:
        item = await sentence_queue.get()
        if item is None:
            break
        yield item

    await producer_task  # propagate exceptions nếu có
