"""Character lore retrieval.

`lore_vectorstore` is the single Chroma collection shared between the ingest
CLI (lore_ingest.py, writes child chunks) and retrieval (this module, reads
them) — both must point at the same collection/persist_directory or nothing
written by one is visible to the other.

`retrieve_character_context()` itself is still a stub (real retrieval lands
in docs/RAG_character_roleplay_implementation_plan.md Stage 4); it currently
returns "" so the LangGraph flow stays runnable while lore_ingest.py (Stage 3)
is being built against `lore_vectorstore`.
"""

from __future__ import annotations

import logging

from langchain_chroma import Chroma

from app.config import settings
from app.memory_store import embeddings

logger = logging.getLogger(__name__)

# Separate collection from `chat_memories` (memory_store.py), same Chroma
# persist_directory — isolation between characters is by `character_id`
# metadata filter, not by a collection per character (see
# docs/RAG_character_roleplay_implementation_plan.md Stage 4).
lore_vectorstore = Chroma(
    collection_name="character_lore_child",
    embedding_function=embeddings,
    persist_directory=settings.chroma_path,
)


async def retrieve_character_context(character_id: str, query: str) -> str:
    logger.debug(
        "No lore store configured; returning empty context for character=%s query=%r.",
        character_id,
        query[:80],
    )
    return ""
