"""Smoke checks for Stage 1 baseline runtime.

Usage:
    python scripts/smoke_baseline.py

Optional live WebSocket turn, only when an LLM provider is already available:
    $env:SMOKE_WS_TURN="1"; python scripts/smoke_baseline.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


def smoke_import() -> None:
    print(f"import_app: ok title={app.title!r}")


def smoke_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        response.raise_for_status()
        payload = response.json()
        print(f"health: ok status={payload.get('status')} tts={payload.get('tts')} stt={payload.get('stt')}")


def smoke_websocket_text_only() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"
            websocket.send_text(json.dumps({
                "type": "user_message",
                "text": "Say hello in one short sentence.",
                "user_id": "smoke_user",
                "session_id": "smoke_session",
                "tts_enabled": False,
                "router_enabled": False,
            }))
            for _ in range(20):
                payload = websocket.receive_json()
                if payload["type"] == "done":
                    print("websocket_text_only: ok")
                    return
                if payload["type"] == "error":
                    raise RuntimeError(payload["message"])
            raise RuntimeError("WebSocket smoke did not receive done payload.")


async def main() -> None:
    smoke_import()
    smoke_health()
    if os.getenv("SMOKE_WS_TURN") == "1":
        smoke_websocket_text_only()
    else:
        print("websocket_text_only: skipped (set SMOKE_WS_TURN=1 when LLM provider is available)")


if __name__ == "__main__":
    asyncio.run(main())
