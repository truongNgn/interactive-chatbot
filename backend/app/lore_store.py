"""Character lore retrieval fallback.

The full character brain store is missing from this checkout. Returning an
empty context keeps the LangGraph flow runnable while preserving the function
contract for Stage 3 tool wrapping.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def retrieve_character_context(character_id: str, query: str) -> str:
    logger.debug(
        "No lore store configured; returning empty context for character=%s query=%r.",
        character_id,
        query[:80],
    )
    return ""
