# Implementation Plan: Character Roleplay + Long-term Memory (RAG)

> Tài liệu này mô tả chi tiết 4 stage để tích hợp short-term history, character persona, ChromaDB long-term memory và emotion-aware RAG vào hệ thống Interactive 3D Chatbot.

## 🔗 Liên kết
- [BRAIN.md](BRAIN.md) — Cấu trúc dự án
- [Developer Log](developer_log.md) — Nhật ký task hiện tại

---

## Dependency Chain

```
Stage 1 — Short-term History + Session Identity
    ├── Stage 2 — Character Persona (song song với Stage 3)
    └── Stage 3 — Long-term Memory: ChromaDB + RAG
                  └── Stage 4 — Emotion Memory + Quality (dedup, rerank, API)
```

---

## Stage 1 — Short-term Memory: Multi-turn History

**Goal:** LLM nhận toàn bộ lịch sử trong session. Fix bug stateless hiện tại.

### Files mới
| File | Mô tả |
|---|---|
| `backend/app/session_store.py` | In-memory `{session_id: [turns]}` với asyncio.Lock, MAX_HISTORY_TURNS |

### Files sửa
| File | Thay đổi |
|---|---|
| `backend/app/config.py` | + `max_history_turns`, `character_name`, `character_persona` |
| `backend/app/models.py` | `UserMessagePayload` + optional `user_id`, `session_id` |
| `backend/app/llm_handler.py` | `stream_tokens(user_text, history=None, memory_context=None)` — build full messages array |
| `backend/app/orchestrator.py` | Nhận `session_store`, `session_id`; get_history trước LLM; append_turn sau |
| `backend/app/main.py` | Khởi tạo SessionStore; parse user_id/session_id; truyền vào orchestrator |
| `frontend/src/store/chatStore.ts` | + `userId` (localStorage), `sessionId` (per mount) |
| `frontend/src/hooks/useWebSocket.ts` | Đính `user_id`, `session_id` vào mọi payload |
| `frontend/src/types/index.ts` | `UserMessagePayload` + optional fields |

### Verification
```bash
wscat -c ws://localhost:8000/ws/chat
> {"type":"user_message","text":"Tôi tên là Minh","user_id":"u1","session_id":"s1"}
> {"type":"user_message","text":"Bạn còn nhớ tên tôi không?","user_id":"u1","session_id":"s1"}
# Expected: avatar nhắc lại "Minh"
```

---

## Stage 2 — Character Persona: Configurable Identity

**Goal:** Avatar có tên, backstory, tính cách cấu hình qua `.env`.

### Files mới
| File | Mô tả |
|---|---|
| `backend/app/persona.py` | `build_persona_block()`, `build_system_prompt(memory_context)` |

### Files sửa
| File | Thay đổi |
|---|---|
| `backend/app/config.py` | + `character_backstory`, `character_personality` |
| `backend/app/llm_handler.py` | Thay hardcoded SYSTEM_PROMPT → `persona.build_system_prompt(memory_context)` |
| `backend/.env.example` | + section `# Character Persona` |

---

## Stage 3 — Long-term Memory: ChromaDB + RAG

**Goal:** Nhớ xuyên session qua ChromaDB vector store.

### New dependency
```
chromadb>=0.5.0
```
```bash
ollama pull nomic-embed-text
```

### Files mới
| File | Mô tả |
|---|---|
| `backend/app/memory_store.py` | ChromaDB PersistentClient, embed(), store_turn(), retrieve_relevant(), format_memory_context() |
| `backend/app/memory_middleware.py` | `enrich_with_memory()`, `persist_exchange()` |

### Files sửa
| File | Thay đổi |
|---|---|
| `backend/app/config.py` | + `chroma_path`, `embedding_model`, `memory_retrieval_count`, `memory_enabled` |
| `backend/app/main.py` | Init MemoryStore trong lifespan; enrich trước LLM; persist sau pipeline |
| `backend/app/orchestrator.py` | `run()` nhận `memory_context: str \| None` → truyền xuống llm_handler |
| `docker-compose.yml` | Volume `chroma_data:/app/chroma_data` |

### Graceful Degradation
- ChromaDB fail → `memory_store = None` → chạy không có memory
- Embed fail → return `[]` → không inject context, không block response

### Verification
```bash
# New session, same user_id → avatar nhắc ký ức cũ
> {"type":"user_message","text":"Dạo này tôi vẫn mệt vì deadline","user_id":"u1","session_id":"s2"}
# Kiểm tra count:
python -c "import chromadb; c=chromadb.PersistentClient('./chroma_data'); print(c.get_collection('chat_memories').count())"
```

---

## Stage 4 — Emotion-aware Memory + Quality

**Goal:** Memory có emotional context; dedup tránh lưu trùng; rerank recency+semantic.

### Files sửa
| File | Thay đổi |
|---|---|
| `backend/app/memory_store.py` | Embed format `"[emotion] role: text"`; `deduplicate()` trước store |
| `backend/app/memory_middleware.py` | Rerank: `score = semantic*(1-w) + recency*w`; giữ top 5 từ 10 candidates |
| `backend/app/config.py` | + `memory_dedup_threshold: 0.95`, `memory_recency_weight: 0.3` |

### Files mới (optional)
| File | Mô tả |
|---|---|
| `backend/app/routers/memory.py` | `GET/DELETE /api/memory/{user_id}`, `GET /api/memory/{user_id}/stats` |

### Verification
```bash
curl http://localhost:8000/api/memory/u1/stats
# Gửi 2 câu gần giống → chỉ 1 entry trong DB (dedup hoạt động)
```

---

*Tạo: 2026-05-11 | Agent: Claude (Senior AI Engineer)*
