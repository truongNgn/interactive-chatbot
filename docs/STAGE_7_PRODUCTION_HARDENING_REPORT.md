# Stage 7 Production Hardening Report

Related: [AI Agent Platform Workflow Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md), [Postgres Production Upgrade Plan](POSTGRES_PRODUCTION_UPGRADE_PLAN.md), [BRAIN.md](../BRAIN.md), [developer_log.md](../developer_log.md).

## Goal

Stage 7 starts moving the backend from prototype mode toward a more production-ready shape without breaking the current WebSocket or frontend contract.

Implemented in this slice:
- Clear auth boundary for REST and WebSocket traffic.
- The backend no longer trusts `user_id` sent by the WebSocket client payload.
- Rate limiting and request size limits for REST and WebSocket paths.
- File-backed session history behind a feature flag, replacing purely in-memory `_session_store` behavior.
- Readiness endpoint that distinguishes `ready` from `degraded`.
- Docker Compose now includes Postgres and a persistent session-history volume.

## New Runtime Flow

```text
Client
  -> WS /ws/chat?token=...
  -> websocket_auth_context()
  -> parse_client_message(authenticated_user_id)
  -> ChatRequest.user_id from auth/dev mode
  -> TurnOrchestrator
  -> LangGraph generate_node
  -> RunnableWithMessageHistory
  -> FileChatMessageHistory(user_id:session_id)
```

REST requests pass through `RateLimitMiddleware`. Feedback rating and debug endpoints resolve the user from the auth context and only return events owned by the current user.

## Module Map

- `backend/app/auth.py`: JWT-compatible HS256 dev token issuing and verification, plus REST/WS auth context helpers.
- `backend/app/rate_limit.py`: fixed-window in-memory REST/WS rate limiter.
- `backend/app/session_history.py`: `FileChatMessageHistory`, `build_history_key(user_id, session_id)`, and readiness probe.
- `backend/app/gateway/schemas.py`: `parse_client_message(..., authenticated_user_id)` ignores client-supplied `user_id`.
- `backend/app/gateway/websocket.py`: WebSocket auth, message size limit, and message rate limit.
- `backend/app/lc_chain.py`: uses `app.session_history.get_session_history`.
- `backend/app/lc_graph.py`: namespaces history as `user_id:session_id`.
- `backend/app/main.py`: `/ready`, `/api/auth/dev-token`, feedback auth filtering, REST rate-limit middleware.
- `backend/app/tts_handler.py`: ElevenLabs SDK import fallback so text-only/backend import does not crash when the optional SDK is broken.

## New Config

```env
AUTH_REQUIRED=false
AUTH_TOKEN_SECRET=change-me-dev-secret
AUTH_TOKEN_EXPIRE_MINUTES=1440
AUTH_DEV_USER_ID=dev_user
MAX_WS_MESSAGE_BYTES=32768
MAX_REST_REQUEST_BYTES=1048576
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
WS_RATE_LIMIT_MESSAGES=60
WS_RATE_LIMIT_WINDOW_SECONDS=60
SESSION_BACKEND=file
SESSION_HISTORY_PATH=./data/session_history
DATABASE_URL=postgresql+asyncpg://chatbot:chatbot@postgres:5432/chatbot
```

## Docker Compose

`docker-compose.yml` now includes:
- `postgres:16-alpine`
- `postgres_data` volume
- `session_history` volume mounted into the backend
- `DATABASE_URL` wired into the backend environment

The full Postgres schema and production auth flow remain part of the next step in [POSTGRES_PRODUCTION_UPGRADE_PLAN.md](POSTGRES_PRODUCTION_UPGRADE_PLAN.md).

## Verification

```powershell
cd backend
$env:UV_CACHE_DIR='D:\Coder-IT\AI\interactive-chatbot\backend\.uv-cache'
uv run --with fastapi==0.115.0 --with pydantic==2.9.2 --with pydantic-settings==2.5.2 --with python-dotenv==1.0.1 --with python-multipart --with httpx --with ollama==0.3.3 --with elevenlabs==1.50.3 --with langchain-core --with langchain-community --with langchain-ollama --with langchain-openai --with langchain-chroma --with chromadb --with rank-bm25 --with langgraph python scripts/smoke_stage7.py
uv run --with fastapi==0.115.0 --with pydantic==2.9.2 --with pydantic-settings==2.5.2 --with python-dotenv==1.0.1 --with python-multipart --with httpx --with ollama==0.3.3 --with elevenlabs==1.50.3 --with langchain-core --with langchain-community --with langchain-ollama --with langchain-openai --with langchain-chroma --with chromadb --with rank-bm25 --with langgraph --with pytest python -m pytest -q tests --basetemp D:\Coder-IT\AI\interactive-chatbot\backend\.pytest-tmp
```

Latest local result:
- `scripts/smoke_stage7.py`: pass.
- Backend regression tests: `15 passed`.
- `/ready` can return `degraded` when Ollama is not running; this is expected and distinct from endpoint failure.

## Remaining Stage 7 Gaps

- Real user registration/login endpoints and password hashing.
- Postgres-backed conversations/messages through SQLAlchemy/Alembic.
- Conversation listing APIs for frontend sidebar restore.
- Redis or another shared rate limiter for multi-process deployments.
- Frontend token storage and login/register UI.
