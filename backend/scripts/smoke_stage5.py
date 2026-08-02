"""Stage 5 smoke wrapper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    result = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "eval_retrieval.py")],
        cwd=BACKEND_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    print(result.stdout.strip())
    print("stage5_smoke: ok")


if __name__ == "__main__":
    main()
