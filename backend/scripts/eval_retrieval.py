"""Offline retrieval eval for Stage 5.

Default mode is dependency-light and does not require Ollama/Chroma. It
evaluates RRF fusion, exact/semantic hit checks, and metadata isolation using
cases from backend/evals/retrieval_cases.jsonl.

Optional live mode:
    $env:RETRIEVAL_EVAL_LIVE="1"; python scripts/eval_retrieval.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from langchain_core.documents import Document

from app.bm25_store import BM25SearchResult
from app.memory_store import _rrf_fusion, hybrid_retrieve_with_metrics

CASES_PATH = BACKEND_ROOT / "evals" / "retrieval_cases.jsonl"


@dataclass
class EvalResult:
    case_id: str
    category: str
    hit: bool
    forbidden_hit: bool
    rank: int | None


def _load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with CASES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def _rank_of(context_lines: list[str], expected_substrings: list[str]) -> int | None:
    for idx, line in enumerate(context_lines, start=1):
        if any(expected in line for expected in expected_substrings):
            return idx
    return None


def _offline_eval_case(case: dict[str, Any]) -> EvalResult:
    user_id = case.get("user_id", "eval_user")
    character_id = case.get("character_id", "luna")
    dense_docs = [
        Document(page_content=text, metadata={"user_id": user_id, "character_id": character_id, "doc_type": "turn"})
        for text in case.get("dense_results", [])
    ]
    sparse_results = [
        BM25SearchResult(
            doc_id=item["doc_id"],
            score=float(item["score"]),
            text=item["text"],
            metadata=item.get("metadata", {}),
        )
        for item in case.get("sparse_results", [])
        if item.get("metadata", {}).get("user_id", user_id) == user_id
        and item.get("metadata", {}).get("character_id", character_id) == character_id
    ]
    fused = _rrf_fusion(dense_docs, sparse_results, top_k=5)
    context_lines = []
    if case.get("facts_context"):
        context_lines.append(case["facts_context"])
    context_lines.extend(fused)

    expected = case.get("expected_substrings", [])
    forbidden = case.get("forbidden_substrings", [])
    rank = _rank_of(context_lines, expected)
    context = "\n".join(context_lines)
    return EvalResult(
        case_id=case["id"],
        category=case["category"],
        hit=rank is not None,
        forbidden_hit=any(item in context for item in forbidden),
        rank=rank,
    )


async def _live_eval_case(case: dict[str, Any]) -> EvalResult:
    context, _metrics = await hybrid_retrieve_with_metrics(
        case.get("user_id", "eval_user"),
        case.get("character_id", "luna"),
        case["query"],
    )
    context = context or ""
    expected = case.get("expected_substrings", [])
    forbidden = case.get("forbidden_substrings", [])
    lines = context.splitlines()
    rank = _rank_of(lines, expected)
    return EvalResult(
        case_id=case["id"],
        category=case["category"],
        hit=rank is not None,
        forbidden_hit=any(item in context for item in forbidden),
        rank=rank,
    )


def _summarize(results: list[EvalResult]) -> dict[str, Any]:
    total = len(results)
    hits = sum(1 for result in results if result.hit)
    forbidden_hits = sum(1 for result in results if result.forbidden_hit)
    reciprocal_ranks = [1 / result.rank for result in results if result.rank]
    return {
        "cases": total,
        "recall_at_5": hits / total if total else 0.0,
        "mrr": sum(reciprocal_ranks) / total if total else 0.0,
        "forbidden_hit_count": forbidden_hits,
        "pass": hits == total and forbidden_hits == 0,
    }


async def main() -> None:
    cases = _load_cases()
    live = os.getenv("RETRIEVAL_EVAL_LIVE") == "1"
    results = []
    for case in cases:
        result = await _live_eval_case(case) if live else _offline_eval_case(case)
        results.append(result)
        status = "PASS" if result.hit and not result.forbidden_hit else "FAIL"
        print(f"{status} {result.case_id} category={result.category} rank={result.rank}")

    summary = _summarize(results)
    print(json.dumps(summary, indent=2))
    if not summary["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
