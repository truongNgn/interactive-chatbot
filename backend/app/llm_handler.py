"""
LLM Handler: quản lý giao tiếp với Ollama (Llama 3).
Trả về async generator các token từ stream.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import ollama

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful and expressive AI assistant with a warm personality.

CRITICAL INSTRUCTION — EMOTION TAGS:
For EVERY sentence you generate, you MUST prepend it with exactly one emotion tag.
Choose from this list only: [joy], [sad], [neutral], [thinking], [surprise], [anger]

Rules:
- One tag per sentence, placed at the very start.
- Match the tag to the emotional tone of that specific sentence.
- Do NOT explain the tags or mention them in conversation.
- Do NOT skip the tag for any sentence, including short responses.

Examples:
[joy] Hello there! How can I help you today?
[thinking] Let me think about that for a moment...
[neutral] The capital of France is Paris.
[surprise] Oh wow, I didn't expect that question!
[sad] I'm sorry to hear you're going through a tough time.
"""


class LLMHandler:
    def __init__(self) -> None:
        self._client = ollama.AsyncClient(host=settings.ollama_host)
        self.model = settings.ollama_model

    async def stream_tokens(self, user_text: str) -> AsyncGenerator[str, None]:
        """
        Gửi message tới Llama 3 và yield từng token từ stream.
        Raises OllamaError nếu model không khả dụng.
        """
        logger.info("LLM stream started | model=%s | input=%r", self.model, user_text[:80])

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        try:
            async for part in await self._client.chat(
                model=self.model,
                messages=messages,
                stream=True,
            ):
                token: str = part["message"]["content"]
                if token:
                    yield token
        except Exception as exc:
            logger.error("LLM stream error: %s", exc)
            raise

    async def health_check(self) -> bool:
        """Kiểm tra Ollama có chạy và model có tồn tại không."""
        try:
            models = await self._client.list()
            available = [m["name"] for m in models.get("models", [])]
            if self.model not in available:
                logger.warning("Model %s not found. Available: %s", self.model, available)
                return False
            return True
        except Exception as exc:
            logger.error("Ollama health check failed: %s", exc)
            return False
