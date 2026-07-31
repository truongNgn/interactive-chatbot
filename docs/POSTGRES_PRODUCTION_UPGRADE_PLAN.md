# Implementation Plan — Nâng cấp Production với PostgreSQL

Mục tiêu: đưa dự án từ "prototype cá nhân" (session sống trong RAM, không auth, không audit) lên mức **junior-production-ready**, với PostgreSQL làm structured data layer đứng cạnh ChromaDB (vector) chứ không thay thế.

Liên quan: [config.py](../backend/app/config.py), [lc_chain.py](../backend/app/lc_chain.py), [lc_graph.py](../backend/app/lc_graph.py), [memory_store.py](../backend/app/memory_store.py), [main.py](../backend/app/main.py), [docker-compose.yml](../docker-compose.yml).

---

## 0. Luồng data hiện tại (đã khảo sát trong code)

```
Frontend (WS /ws/chat)
   │  {type:"user_message", text, user_id, session_id, character_id, voice, tts_enabled}
   ▼
main.py: websocket_chat → Orchestrator.run()
   │
   ▼
lc_graph.py: LangGraph "graph.ainvoke"
   ├─ retrieve_memories_node      → memory_store.hybrid_retrieve()  → Chroma (dense) + BM25 (in-memory, sparse)
   ├─ retrieve_character_context_node → lore_store (character lore, Chroma riêng)
   ├─ build_prompt_node           → persona.build_system_prompt()
   ├─ generate_node               → lc_chain.build_chain() → ChatOllama/ChatOpenAI streaming
   │        │
   │        └─ RunnableWithMessageHistory dùng get_session_history(session_id)
   │              → _session_store: dict[str, ChatMessageHistory]  ⚠️ THUẦN IN-MEMORY
   └─ store_memories_node         → memory_middleware.schedule_persist() → memory_store.store_turn() → Chroma + BM25 mirror
   ▼
Orchestrator → sentence buffering → TTS → Rhubarb visemes → WebSocket gửi AudioChunkPayload
```

**Nơi lưu trữ hiện tại:**
| Data | Nơi lưu | Sống sót qua restart? |
|---|---|---|
| Lịch sử hội thoại trong 1 session (dùng làm context cho LLM) | `_session_store` dict trong RAM ([lc_chain.py:20](../backend/app/lc_chain.py:20)) | ❌ Mất khi restart backend |
| Turn memory dài hạn (semantic search) | ChromaDB `chroma_data/` | ✅ |
| Facts (tên, sở thích user) | ChromaDB (`doc_type=fact`) | ✅ |
| BM25 sparse index | RAM, rebuild từ Chroma khi restart | ✅ (rebuild được) |
| User identity | Chuỗi tự do `user_id` client tự gửi, **không xác thực** | — |
| Danh sách session/conversation của 1 user | **Không tồn tại** — FE không có cách liệt kê lại các cuộc chat cũ | — |

### Vấn đề chính cần Postgres giải quyết
1. **Session history mất khi restart backend** — đây là gap nghiêm trọng nhất cho production.
2. **Không có user account thật** — `user_id` client tự đặt, không auth, không phân quyền, dễ giả mạo id người khác để đọc "facts" của họ.
3. **Không thể liệt kê lịch sử hội thoại** (sidebar "Recent chats" kiểu ChatGPT là bất khả thi với kiến trúc hiện tại).
4. **Không có audit/analytics**: không biết ai chat khi nào, bao nhiêu turn, bao nhiêu lỗi.
5. Chroma phù hợp cho **similarity search**, không phù hợp cho **quan hệ + truy vấn chính xác** (list theo user, phân trang, JOIN).

---

## 1. Kiến trúc đề xuất

```
                         ┌─────────────────────┐
                         │      PostgreSQL       │
                         │  users / sessions /    │
                         │  messages / refresh_   │
                         │  tokens                │
                         └──────────┬────────────┘
                                    │ asyncpg + SQLAlchemy async
                                    ▼
FastAPI backend  ──►  AuthMiddleware (JWT)  ──►  ChatService
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                                ▼
          get_session_history(session_id)     ChromaDB (không đổi)
          → đọc/ghi Postgres `messages`        - long-term semantic memory
          thay vì dict RAM                      - character lore
```

Nguyên tắc phân việc rõ ràng, **không migrate Chroma sang Postgres**:
- **Postgres** = structured, quan hệ, cần đúng 100% (users, auth, session/message log, quota).
- **Chroma** = vector similarity search (long-term memory, lore) — giữ nguyên.

---

## 2. Schema đề xuất

```sql
-- users: auth thật thay cho user_id tự khai
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,       -- bcrypt/argon2
    display_name  VARCHAR(100),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- conversations: 1 row = 1 session_id hiện có trong code
CREATE TABLE conversations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id  VARCHAR(50) NOT NULL,
    title         VARCHAR(200),               -- auto-gen từ tin nhắn đầu
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC);

-- messages: thay thế _session_store (ChatMessageHistory) trong RAM
CREATE TABLE messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL CHECK (role IN ('human','ai')),
    content         TEXT NOT NULL,
    emotion         VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- refresh_tokens: JWT refresh flow (nếu làm auth đầy đủ)
CREATE TABLE refresh_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked    BOOLEAN NOT NULL DEFAULT false
);
```

`user_id`/`session_id` hiện tại trong `ChatState`, `memory_store.py` (dùng làm metadata filter cho Chroma) **giữ nguyên kiểu string** — map trực tiếp sang `users.id`/`conversations.id` dạng UUID string, không cần đổi API của Chroma.

---

## 3. Thay đổi trong code (theo file)

| File | Thay đổi |
|---|---|
| `backend/app/db.py` *(mới)* | SQLAlchemy async engine (`asyncpg`), session factory, `Base` |
| `backend/app/db_models.py` *(mới)* | ORM models: `User`, `Conversation`, `Message`, `RefreshToken` |
| `backend/alembic/` *(mới)* | Alembic migrations — schema versioning, bắt buộc cho production |
| `backend/app/auth.py` *(mới)* | Đăng ký/login, hash password (`passlib[bcrypt]`), JWT issue/verify (`python-jose`) |
| `backend/app/lc_chain.py` | `get_session_history()` đổi từ dict RAM sang `PostgresChatMessageHistory` (đọc/ghi bảng `messages`), dùng `conversation_id` |
| `backend/app/main.py` | Thêm REST: `POST /auth/register`, `POST /auth/login`, `GET /api/conversations`, `GET /api/conversations/{id}/messages`; WebSocket handshake yêu cầu JWT (query param hoặc header khi connect) |
| `backend/app/memory_middleware.py` | Không đổi logic Chroma, nhưng `user_id` truyền vào giờ là UUID thật từ JWT thay vì client tự khai |
| `backend/.env.example`, `config.py` | Thêm `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES` |
| `docker-compose.yml` | Thêm service `postgres:16-alpine` + volume `postgres_data`, `backend` thêm `depends_on: postgres` |
| `frontend/` | Thêm màn login/register, lưu JWT (localStorage), gửi kèm khi mở WebSocket, sidebar "Recent conversations" gọi `GET /api/conversations` |

---

## 4. Thứ tự triển khai (từng PR nhỏ, không đổi hết 1 lần)

1. **Hạ tầng**: thêm Postgres vào `docker-compose.yml`, viết `db.py` + `db_models.py` + Alembic init migration. Chạy được `alembic upgrade head` là xong bước này — chưa đổi logic chat.
2. **Conversation history vào Postgres** (gap nghiêm trọng nhất): viết `PostgresChatMessageHistory` implement interface của LangChain `BaseChatMessageHistory`, thay `get_session_history()`. Test: restart backend giữa chừng hội thoại, lịch sử vẫn còn.
3. **Auth tối thiểu**: bảng `users`, endpoint register/login, JWT. WebSocket bắt buộc token hợp lệ, lấy `user_id` từ token thay vì trust client field `user_id` như hiện tại ([main.py:346](../backend/app/main.py:346) đang nhận `user_id` trực tiếp từ payload — lỗ hổng giả mạo).
4. **Conversation listing API**: `GET /api/conversations`, `GET /api/conversations/{id}/messages`, tự tạo row `conversations` khi user bắt đầu session mới.
5. **Frontend**: login form + lưu token + sidebar lịch sử chat.
6. **(Optional, sau)**: dọn `store_fact`/`store_character_fact` trong Chroma — cân nhắc chuyển facts có cấu trúc rõ (tên, nghề nghiệp) sang bảng Postgres `user_facts` để query chính xác thay vì similarity search; giữ Chroma cho phần thật sự cần semantic (turn memory, lore).

---

## 5. Rủi ro / lưu ý

- **Không xoá `_session_store` ngay** — giữ song song, feature-flag qua `settings.session_backend = "memory" | "postgres"` trong giai đoạn 2, rollback nhanh nếu lỗi.
- **Migration path cho dữ liệu Chroma cũ**: facts/turns hiện tại gắn với `user_id` dạng chuỗi tự do (vd. `"default_user"`) — cần script gán các `user_id` cũ này cho 1 tài khoản "legacy" thật trong Postgres, tránh mất dữ liệu khi bật auth bắt buộc.
- **Không tự roll JWT bằng tay** — dùng thư viện đã kiểm chứng (`python-jose` hoặc `pyjwt`), secret nằm trong `.env`, không commit.
- Alembic là bắt buộc ngay từ đầu, kể cả dự án nhỏ — tránh kiểu "sửa schema tay trên prod" sau này.

---

## 6. Definition of Done

- [ ] `docker-compose up` chạy được Postgres, backend tự áp migration khi start (hoặc CI chạy `alembic upgrade head`)
- [ ] Restart backend giữa hội thoại → lịch sử chat vẫn còn khi tiếp tục
- [ ] Không còn endpoint nào tin tưởng `user_id` do client tự khai trong payload
- [ ] Có thể đăng ký/đăng nhập, list được các cuộc hội thoại cũ của chính mình
- [ ] `.env.example` cập nhật đủ biến mới, không có secret thật commit vào git
