"""Stage 6 CI-like smoke command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> None:
    result = subprocess.run(args, cwd=BACKEND_ROOT, text=True, capture_output=True)
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    _run([sys.executable, "-m", "pytest", "-q"])
    _run([sys.executable, "scripts/eval_retrieval.py"])
    _run([sys.executable, "scripts/eval_answer_quality.py"])
    print("stage6_smoke: ok")


if __name__ == "__main__":
    main()
