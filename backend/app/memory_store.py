"""LangChain Chroma memory store + BM25 mirror for hybrid retrieval."""

import logging
import time

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

from app.config import settings
from app.bm25_store import bm25_store, BM25SearchResult

logger = logging.getLogger(__name__)

embeddings = OllamaEmbeddings(
    model=settings.embedding_model,
    base_url=settings.ollama_host,
)

vectorstore = Chroma(
    collection_name="chat_memories",
    embedding_function=embeddings,
    persist_directory=settings.chroma_path,
)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def _mirror_to_bm25(doc_id: str, text: str, metadata: dict) -> None:
    """Mirror a document to the BM25 store immediately after ChromaDB write."""
    try:
        bm25_store.add_document(doc_id, text, metadata)
        logger.debug("BM25 mirror: %s", text[:60])
    except Exception as e:
        logger.warning("BM25 mirror failed (non-fatal): %s", e)


async def store_turn(user_id: str, session_id: str, role: str, text: str, emotion: str) -> None:
    if not settings.memory_enabled:
        return

    content = f"[{emotion}] {role}: {text}"
    doc_id = f"{user_id}_{session_id}_{role}_{int(time.time() * 1000)}"
    metadata = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": time.time(),
        "role": role,
        "doc_type": "turn",
    }
    doc = Document(page_content=content, metadata=metadata)
    try:
        await vectorstore.aadd_documents([doc])
        _mirror_to_bm25(doc_id, content, metadata)
        logger.debug("Stored memory for %s: %s", role, text[:40])
    except Exception as e:
        logger.warning("Memory store failed: %s", e)


async def store_fact(user_id: str, fact_type: str, fact_value: str) -> None:
    """Store a structured fact extracted from conversation (e.g. user's name, job)."""
    if not settings.memory_enabled:
        return

    content = f"[FACT] {fact_type}: {fact_value}"
    try:
        # Deduplicate: skip if identical fact already stored
        existing = await vectorstore.asimilarity_search(
            query=content,
            k=1,
            filter={"$and": [{"user_id": user_id}, {"doc_type": "fact"}, {"fact_type": fact_type}]},
        )
        if existing and existing[0].page_content == content:
            logger.debug("Fact already stored: %s=%s", fact_type, fact_value)
            return

        doc_id = f"{user_id}_fact_{fact_type}"
        metadata = {
            "user_id": user_id,
            "timestamp": time.time(),
            "doc_type": "fact",
            "fact_type": fact_type,
        }
        doc = Document(page_content=content, metadata=metadata)
        await vectorstore.aadd_documents([doc])
        _mirror_to_bm25(doc_id, content, metadata)
        logger.info("Stored fact [%s] = %s for user %s", fact_type, fact_value, user_id)
    except Exception as e:
        logger.warning("Fact store failed: %s", e)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

async def retrieve_facts(user_id: str) -> str | None:
    """Retrieve all structured facts about the user — always injected into context."""
    if not settings.memory_enabled:
        return None
    try:
        docs = await vectorstore.asimilarity_search(
            query="user personal information name job interest",
            k=20,
            filter={"$and": [{"user_id": user_id}, {"doc_type": "fact"}]},
        )
        if not docs:
            return None
        lines = [doc.page_content for doc in docs]
        return "Known facts about the user:\n" + "\n".join(f"- {l}" for l in lines)
    except Exception as e:
        logger.warning("Fact retrieval failed: %s", e)
        return None


async def retrieve_memories(user_id: str, query: str, k: int = 5) -> str | None:
    """Dense-only retrieval (ChromaDB). Kept for backward compatibility."""
    if not settings.memory_enabled:
        return None

    parts: list[str] = []

    facts = await retrieve_facts(user_id)
    if facts:
        parts.append(facts)

    try:
        docs = await vectorstore.asimilarity_search(
            query=query,
            k=k,
            filter={"user_id": user_id},
        )
        turn_docs = [d for d in docs if d.metadata.get("doc_type") != "fact"]
        if turn_docs:
            turns = "\n".join(f"- {doc.page_content}" for doc in turn_docs)
            parts.append("Relevant past conversation:\n" + turns)
    except Exception as e:
        logger.warning("Memory retrieval failed: %s", e)

    return "\n\n".join(parts) if parts else None


def _rrf_fusion(
    dense_results: list[Document],
    sparse_results: list[BM25SearchResult],
    k: int = 60,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.5,
    top_k: int = 5,
) -> list[str]:
    """
    Reciprocal Rank Fusion: combine dense (ChromaDB) and sparse (BM25) results.

    sparse_weight > dense_weight because dense search already handles semantics
    well; BM25 bonus is the marginal gain for exact keyword matches.

    Returns a list of page_content strings ready for prompt injection.
    """
    scores: dict[str, float] = {}
    texts: dict[str, str] = {}

    for rank, doc in enumerate(dense_results, start=1):
        key = doc.page_content
        scores[key] = scores.get(key, 0.0) + dense_weight / (k + rank)
        texts[key] = doc.page_content

    for rank, result in enumerate(sparse_results, start=1):
        key = result.text
        scores[key] = scores.get(key, 0.0) + sparse_weight / (k + rank)
        texts[key] = result.text

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [texts[key] for key, _ in ranked[:top_k]]


async def hybrid_retrieve(user_id: str, query: str, k: int = 5) -> str | None:
    """
    Hybrid retrieval: BM25 sparse + ChromaDB dense, fused via RRF.

    Facts are always prepended (not fused — they are retrieved by filter,
    not by relevance, so ranking doesn't apply).
    """
    if not settings.memory_enabled:
        return None

    parts: list[str] = []

    # 1. Always fetch structured facts first (unchanged from original)
    facts = await retrieve_facts(user_id)
    if facts:
        parts.append(facts)

    # 2. Dense retrieval — over-fetch for better RRF coverage
    dense_docs: list[Document] = []
    try:
        dense_docs = await vectorstore.asimilarity_search(
            query=query,
            k=k * 2,
            filter={"user_id": user_id},
        )
        # Exclude fact documents — already handled above
        dense_docs = [d for d in dense_docs if d.metadata.get("doc_type") != "fact"]
    except Exception as e:
        logger.warning("Dense retrieval failed: %s", e)

    # 3. Sparse (BM25) retrieval — filter by user_id in metadata
    sparse_results: list[BM25SearchResult] = []
    try:
        all_sparse = bm25_store.search(query, top_k=k * 2)
        sparse_results = [
            r for r in all_sparse
            if r.metadata.get("user_id") == user_id
            and r.metadata.get("doc_type") != "fact"
        ]
    except Exception as e:
        logger.warning("BM25 retrieval failed (non-fatal): %s", e)

    # 4. Fuse results
    if not dense_docs and not sparse_results:
        return "\n\n".join(parts) if parts else None

    fused = _rrf_fusion(dense_docs, sparse_results, top_k=k)
    if fused:
        turns = "\n".join(f"- {text}" for text in fused)
        parts.append("Relevant past conversation:\n" + turns)

    logger.debug(
        "hybrid_retrieve: dense=%d sparse=%d fused=%d bm25_store_size=%d",
        len(dense_docs), len(sparse_results), len(fused), bm25_store.size(),
    )

    return "\n\n".join(parts) if parts else None
