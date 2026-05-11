"""
Orchestrator: nhận token stream từ LLM, gom câu (sentence-buffering),
bóc tách emotion tag, yield SentenceChunk vào queue cho Stage 2.

Chiến lược flush để tối ưu latency:
  - Câu đầu tiên (first_chunk): flush ngay ở dấu phẩy/xuống dòng nếu >= 15 ký tự
    → user nghe audio đầu tiên sớm nhất có thể
  - Các câu sau: flush ở dấu câu (.!?) hoặc dấu phẩy nếu >= 80 ký tự
    → câu dài hơn = ít TTS calls hơn = mượt hơn
"""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator

from app.llm_handler import BaseLLMHandler, get_llm_handler
from app.models import Emotion, SentenceChunk

logger = logging.getLogger(__name__)

# Regex bắt emotion tag ở đầu chuỗi: [joy], [sad], v.v.
_EMOTION_TAG_RE = re.compile(
    r"^\s*\[(joy|sad|neutral|thinking|surprise|anger)\]\s*",
    re.IGNORECASE,
)

# Ký tự kết thúc câu (tiếng Anh & Việt)
_SENTENCE_END_RE = re.compile(r"[.!?。？！]+")

# Dấu phân cách phụ — flush tùy theo ngưỡng
_CLAUSE_END_RE = re.compile(r"[,;\n—\-–]+")

# Ngưỡng flush:
# - Chunk đầu tiên: 15 ký tự → user nghe audio sớm
# - Chunk tiếp theo: 80 ký tự → câu đủ dài, giảm số lần gọi TTS
_FIRST_CLAUSE_LEN = 15
_NORMAL_CLAUSE_LEN = 80


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


def _should_flush(buffer: str, char: str, is_first_chunk: bool) -> bool:
    """
    Quyết định có nên flush buffer thành câu không.
    is_first_chunk=True → ngưỡng thấp hơn để audio đầu xuất hiện sớm.
    """
    # Luôn flush khi gặp dấu kết thúc câu
    if _SENTENCE_END_RE.search(char):
        return True

    # Flush theo dấu phụ (phẩy, xuống dòng, em-dash...)
    if _CLAUSE_END_RE.search(char):
        threshold = _FIRST_CLAUSE_LEN if is_first_chunk else _NORMAL_CLAUSE_LEN
        if len(buffer) >= threshold:
            return True

    return False


class Orchestrator:
    def __init__(self, llm_handler: BaseLLMHandler | None = None) -> None:
        self._llm = llm_handler or get_llm_handler()
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
        first_chunk = True  # chunk đầu tiên dùng ngưỡng thấp hơn

        try:
            async for token in self._llm.stream_tokens(user_text):
                if self._interrupted:
                    logger.info("Stream interrupted, stopping token consumption")
                    break

                buffer += token

                if buffer and _should_flush(buffer, buffer[-1], is_first_chunk=first_chunk):
                    chunk = _flush_buffer(buffer)
                    if chunk:
                        logger.debug(
                            "Flushed chunk [first=%s]: emotion=%s len=%d text=%r",
                            first_chunk, chunk.emotion, len(chunk.text), chunk.text[:60],
                        )
                        await sentence_queue.put(chunk)
                        first_chunk = False
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
    orchestrator = Orchestrator()
    producer_task = asyncio.create_task(
        orchestrator.run(user_text, sentence_queue)
    )
    while True:
        item = await sentence_queue.get()
        if item is None:
            break
        yield item
    await producer_task
