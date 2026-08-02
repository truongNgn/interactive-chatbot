"""Small in-memory fixed-window rate limiter for Stage 7 hardening."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0 or window_seconds <= 0:
            return True
        now = time.monotonic()
        bucket = self._buckets[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


default_rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_rest_request_bytes:
            return Response("Request body too large.", status_code=413)

        host = request.client.host if request.client else "unknown"
        key = f"rest:{host}"
        if not default_rate_limiter.allow(
            key,
            settings.rate_limit_requests,
            settings.rate_limit_window_seconds,
        ):
            return Response("Rate limit exceeded.", status_code=429)
        return await call_next(request)


def allow_ws_message(websocket: WebSocket, user_id: str) -> bool:
    if not settings.rate_limit_enabled:
        return True
    host = websocket.client.host if websocket.client else "unknown"
    key = f"ws:{user_id}:{host}"
    return default_rate_limiter.allow(
        key,
        settings.ws_rate_limit_messages,
        settings.ws_rate_limit_window_seconds,
    )
