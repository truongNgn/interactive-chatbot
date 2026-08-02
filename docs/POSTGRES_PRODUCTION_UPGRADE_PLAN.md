# Implementation Plan - PostgreSQL Production Upgrade

Goal: move the project from a personal prototype toward a junior-production-ready backend by adding PostgreSQL as the structured data layer next to ChromaDB. PostgreSQL should not replace Chroma; it should own relational data that must be exact, auditable, and permissioned.

Related: [config.py](../backend/app/config.py), [lc_chain.py](../backend/app/lc_chain.py), [lc_graph.py](../backend/app/lc_graph.py), [memory_store.py](../backend/app/memory_store.py), [main.py](../backend/app/main.py), [docker-compose.yml](../docker-compose.yml), [Stage 7 Report](STAGE_7_PRODUCTION_HARDENING_REPORT.md).

## 0. Current Data Flow

```text
Frontend (WS /ws/chat)
  -> Gateway auth + payload normalization
  -> TurnOrchestrator
  -> LangGraph
     -> retrieve_memories_node
        -> memory_store.hybrid_retrieve()
        -> Chroma dense retrieval + BM25 sparse retrieval
     -> retrieve_character_context_node
        -> lore_store
     -> build_prompt_node
     -> generate_node
        -> lc_chain.build_chain()
        -> RunnableWithMessageHistory
        -> get_session_history(user_id:session_id)
     -> store_memories_node
        -> memory_middleware.schedule_persist()
        -> Chroma + BM25 mirror
  -> sentence buffering
  -> TTS / text-only fallback
  -> Rhubarb visemes
  -> WebSocket audio_chunk/done/error
```

Current storage:

| Data | Current Storage | Survives Restart? |
|---|---|---|
| Per-session chat history used by the LLM | Stage 7 file-backed JSONL history, or memory mode by feature flag | Yes in `SESSION_BACKEND=file` |
| Long-term semantic turn memory | ChromaDB `chroma_data/` | Yes |
| Structured extracted facts | ChromaDB metadata/docs | Yes |
| Sparse BM25 index | RAM, mirrored/rebuilt at runtime | Rebuildable |
| User identity | Stage 7 dev/JWT-compatible auth context | Partially |
| Conversation list for a user | PostgreSQL `conversations` table | Yes |
| Audit and analytics | JSONL feedback events | Partially |

## 1. Current Implementation Status

Completed MVP:
- `users`, `conversations`, and `messages` SQLAlchemy models.
- Register/login endpoints with PBKDF2 password hashing.
- JWT-compatible bearer token issuing through the existing auth helper.
- Authenticated conversation list/detail/delete endpoints.
- WebSocket turns persist human and assistant messages to Postgres when the authenticated user exists.
- Frontend login/register/logout panel.
- Frontend bearer token storage and tokenized WebSocket connection.
- Frontend server-side conversation restore after login or page reload.

Still pending:
- Alembic migrations instead of dev auto-create.
- Refresh-token rotation.
- Postgres-backed feedback/audit tables.
- Redis/shared rate limiter.

## 2. Problems PostgreSQL Should Solve

1. **Durable conversation history:** file-backed history is a useful bridge, but production should store conversations/messages in a transactional database.
2. **Real user accounts:** Stage 7 no longer trusts payload `user_id`, but register/login/password hashing is still missing.
3. **Conversation listing:** the frontend cannot restore server-side conversation lists yet.
4. **Auditability:** production needs structured records for user actions, messages, feedback, errors, and moderation outcomes.
5. **Exact relational queries:** Chroma is good for semantic search; Postgres is better for ownership, pagination, joins, quotas, and compliance workflows.

## 3. Target Architecture

```text
FastAPI backend
  -> AuthMiddleware / dependency
  -> ChatService
       -> PostgreSQL
          - users
          - conversations
          - messages
          - feedback_events
          - feedback_ratings
          - audit_logs
       -> ChromaDB
          - long-term semantic memory
          - character lore
```

Rules:
- **Postgres** owns structured, relational, permissioned data.
- **ChromaDB** remains the semantic retrieval layer.
- Existing `user_id` and `session_id` values in `ChatState` can remain strings, but production should use UUID strings derived from database rows.

## 4. Proposed Schema

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id VARCHAR(50) NOT NULL,
    title VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL CHECK (role IN ('human', 'ai')),
    content TEXT NOT NULL,
    emotion VARCHAR(20),
    turn_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

CREATE TABLE feedback_events (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID,
    turn_id UUID,
    event_type VARCHAR(80) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feedback_ratings (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID,
    turn_id UUID NOT NULL,
    rating VARCHAR(20) NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    action VARCHAR(120) NOT NULL,
    resource_type VARCHAR(80),
    resource_id VARCHAR(120),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 5. Code Changes

| File / Area | Change |
|---|---|
| `backend/app/db.py` | Add async SQLAlchemy engine, session factory, and `Base`. |
| `backend/app/db_models.py` | Add ORM models for `User`, `Conversation`, `Message`, `FeedbackEvent`, `FeedbackRating`, `RefreshToken`, `AuditLog`. |
| `backend/alembic/` | Add Alembic migrations for schema versioning. |
| `backend/app/auth.py` | Replace or extend dev-token helpers with password hashing, JWT issuing, refresh-token support. |
| `backend/app/lc_chain.py` | Add `PostgresChatMessageHistory` behind `SESSION_BACKEND=postgres`. |
| `backend/app/main.py` | Add register/login, conversation list, conversation messages, and authenticated WebSocket enforcement. |
| `backend/app/memory_middleware.py` | Keep Chroma behavior, but ensure `user_id` is the authenticated UUID string. |
| `backend/app/feedback/store.py` | Add Postgres-backed feedback store behind a feature flag. |
| `backend/.env.example` | Add DB/auth/session variables. |
| `docker-compose.yml` | Already includes Postgres in Stage 7; add migration startup command or documented migration step. |
| `frontend/` | Add login/register UI, token storage, WebSocket token passing, and server-side conversation restore. |

## 6. Incremental Implementation Order

1. **Database infrastructure:** add SQLAlchemy async engine, ORM models, Alembic config, and first migration.
2. **Conversation/message persistence:** implement `PostgresChatMessageHistory`; keep `SESSION_BACKEND=file|memory|postgres` for rollback.
3. **Auth endpoints:** add register/login, password hashing, JWT access tokens, refresh tokens.
4. **WebSocket enforcement:** when `AUTH_REQUIRED=true`, require a valid token and derive `user_id` from it.
5. **Conversation listing APIs:** add `GET /api/conversations` and `GET /api/conversations/{id}/messages`.
6. **Feedback persistence:** move feedback events/ratings from JSONL to Postgres behind a feature flag.
7. **Frontend auth flow:** add login/register and server-side conversation history restore.
8. **Migration from legacy data:** map old free-form user IDs to a real legacy account if needed.

## 7. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Breaking current chat behavior | Keep `SESSION_BACKEND=file` as the default bridge until Postgres history is proven. |
| Data leakage between users | Always derive `user_id` from auth context and filter by authenticated owner. |
| Manual schema drift | Use Alembic from the first Postgres schema change. |
| Weak JWT implementation | Use a proven library such as `python-jose` or `PyJWT` for production auth. |
| Secrets in source control | Keep secrets in `.env`; never commit real keys. |
| Chroma metadata compatibility | Keep Chroma IDs as strings and map DB UUIDs to string metadata. |

## 8. Definition Of Done

- [x] `docker compose up` includes Postgres and backend wiring.
- [ ] Alembic migration creates all required tables.
- [x] Backend can register and log in a user.
- [x] WebSocket can authenticate via bearer token query parameter.
- [x] Restarting backend does not lose Postgres conversations/messages.
- [x] User A cannot read User B's conversations through conversation APIs.
- [x] Frontend can list and restore the authenticated user's conversations.
- [x] `.env.example` documents all new variables without real secrets.
