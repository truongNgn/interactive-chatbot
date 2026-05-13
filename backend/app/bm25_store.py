"""In-memory BM25 store — sparse keyword retrieval, mirrors ChromaDB writes."""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


@dataclass
class BM25SearchResult:
    doc_id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


class BM25Store:
    """
    Thread-safe in-memory BM25 index.

    Mirrors documents written to ChromaDB so that hybrid_retrieve()
    can combine sparse + dense results via RRF fusion.
    Data is lost on server restart — index is rebuilt from ChromaDB on
    first retrieve if needed (lazy warm-up not implemented yet; cold-start
    means BM25 contributes nothing until documents accumulate this session).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # doc_id → {"text": str, "tokens": list[str], "metadata": dict}
        self._docs: dict[str, dict[str, Any]] = {}
        self._index: BM25Okapi | None = None
        self._ordered_ids: list[str] = []  # same order as BM25 corpus

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def add_document(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        tokens = _tokenize(text)
        if not tokens:
            return
        with self._lock:
            self._docs[doc_id] = {
                "text": text,
                "tokens": tokens,
                "metadata": metadata or {},
            }
            self._index = None  # invalidate — rebuilt lazily on next search

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id not in self._docs:
                return False
            del self._docs[doc_id]
            self._index = None
            return True

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()
            self._index = None
            self._ordered_ids = []

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[BM25SearchResult]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        with self._lock:
            if not self._docs:
                return []

            if self._index is None:
                self._rebuild_index()

            scores = self._index.get_scores(query_tokens)

        results: list[BM25SearchResult] = []
        for idx, score in enumerate(scores):
            if score <= 0:
                continue
            doc_id = self._ordered_ids[idx]
            doc = self._docs[doc_id]
            results.append(BM25SearchResult(
                doc_id=doc_id,
                score=float(score),
                text=doc["text"],
                metadata=doc["metadata"],
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def size(self) -> int:
        return len(self._docs)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_index(self) -> None:
        """Must be called with self._lock held."""
        self._ordered_ids = list(self._docs.keys())
        corpus = [self._docs[doc_id]["tokens"] for doc_id in self._ordered_ids]
        self._index = BM25Okapi(corpus)
        logger.debug("BM25 index rebuilt: %d documents", len(corpus))


# Module-level singleton — mirrors the ChromaDB vectorstore singleton
bm25_store = BM25Store()
