"""Entry point — chạy: python run.py"""
import os
from pathlib import Path

import uvicorn

BACKEND_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(BACKEND_ROOT / ".cache" / "matplotlib"))

from app.config import settings  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        reload_dirs=[str(BACKEND_ROOT / "app")] if settings.reload else None,
        log_level=settings.log_level.lower(),
    )
