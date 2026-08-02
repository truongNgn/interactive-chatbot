"""Rule-based answer quality eval for Stage 6.

This is intentionally offline and deterministic. It checks golden answers for
expected facts/context and obvious forbidden leakage.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = BACKEND_ROOT / "evals" / "answer_quality_cases.jsonl"
USER_NICKNAME = os.getenv("EVAL_USER_NICKNAME", "Johnny")
USER_NICKNAME_PLACEHOLDER = "{{USER_NICKNAME}}"


def _resolve_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(USER_NICKNAME_PLACEHOLDER, USER_NICKNAME)
    if isinstance(value, list):
        return [_resolve_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_placeholders(item) for key, item in value.items()}
    return value


def load_cases() -> list[dict]:
    with CASES_PATH.open("r", encoding="utf-8") as f:
        return [_resolve_placeholders(json.loads(line)) for line in f if line.strip()]


def evaluate_case(case: dict) -> dict:
    answer = case["answer"]
    expected = case.get("expected_substrings", [])
    forbidden = case.get("forbidden_substrings", [])
    expected_hit = all(item.lower() in answer.lower() for item in expected)
    forbidden_hit = any(item.lower() in answer.lower() for item in forbidden)
    return {
        "id": case["id"],
        "pass": expected_hit and not forbidden_hit,
        "expected_hit": expected_hit,
        "forbidden_hit": forbidden_hit,
    }


def main() -> None:
    results = [evaluate_case(case) for case in load_cases()]
    for result in results:
        print(f"{'PASS' if result['pass'] else 'FAIL'} {result['id']}")
    summary = {
        "cases": len(results),
        "pass_count": sum(1 for result in results if result["pass"]),
        "pass": all(result["pass"] for result in results),
    }
    print(json.dumps(summary, indent=2))
    if not summary["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
