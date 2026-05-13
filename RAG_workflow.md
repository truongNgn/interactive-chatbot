# RAG Workflow — LangChain × LangGraph × LangSmith

> Tài liệu mô tả toàn bộ luồng Retrieval-Augmented Generation (RAG) của hệ thống,
> từ lúc người dùng gửi tin nhắn đến khi phản hồi được sinh ra và ký ức được lưu trữ.
> Xem thêm: [BRAIN.md](BRAIN.md) · [WORKFLOW.md](WORKFLOW.md) · [implement_roleplay_langchain.md](implement_roleplay_langchain.md)

---

## 1. Tổng quan kiến trúc RAG

Hệ thống sử dụng ba framework LangChain để xây dựng pipeline RAG hoàn chỉnh:

| Framework | Vai trò | Thành phần cụ thể |
|-----------|---------|-------------------|
| **LangChain** | Công cụ (components) | `ChatOllama`, `OllamaEmbeddings`, `Chroma`, `ChatPromptTemplate`, `RunnableWithMessageHistory` |
| **LangGraph** | Điều phối (orchestration) | `StateGraph` với 4 node: retrieve → build_prompt → generate → store |
| **LangSmith** | Quan sát (observability) | Tracing toàn bộ pipeline, timeline per node, rendered prompt, similarity scores |

```
┌──────────────────────────────────────────────────────────────────┐
│                     BROWSER (Frontend)                           │
│                                                                  │
│  useWebSocket ────► ws.send({ type: "user_message",             │
│                               text, user_id, session_id })       │
└────────────────────────────┬─────────────────────────────────────┘
                             │  WebSocket
┌────────────────────────────▼─────────────────────────────────────┐
│                     SERVER (Backend)                             │
│                                                                  │
│  FastAPI /ws/chat                                                │
│       │                                                          │
│       ▼                                                          │
│  Orchestrator ──► LangGraph StateGraph.ainvoke()                 │
│       │                                                          │
│       │     ┌───────────────────────────────────────────────┐    │
│       │     │ Node 1: retrieve_memories                     │    │
│       │     │   OllamaEmbeddings(nomic-embed-text)          │    │
│       │     │   → embed user_text → vector 768-d            │    │
│       │     │   → Chroma.similarity_search(k=5)             │    │
│       │     │   → filter by user_id metadata                │    │
│       │     │   → memory_context: str | None                │    │
│       │     └───────────────────┬───────────────────────────┘    │
│       │                         │                                │
│       │     ┌───────────────────▼───────────────────────────┐    │
│       │     │ Node 2: build_prompt                          │    │
│       │     │   persona_block ← build_persona_block()       │    │
│       │     │     "You are {name}. {backstory}.             │    │
│       │     │      Personality: {traits}"                   │    │
│       │     │   emotion_rules ← EMOTION_RULES               │    │
│       │     │   memory_context ← Node 1 output              │    │
│       │     │   → Render ChatPromptTemplate                 │    │
│       │     └───────────────────┬───────────────────────────┘    │
│       │                         │                                │
│       │     ┌───────────────────▼───────────────────────────┐    │
│       │     │ Node 3: generate                              │    │
│       │     │   ChatOllama(llama3:8b).astream()             │    │
│       │     │   → token streaming via asyncio.Queue         │    │
│       │     │   → RunnableWithMessageHistory injects        │    │
│       │     │     session history (multi-turn memory)       │    │
│       │     │   → _parse_emotion() bóc [emotion] tag        │    │
│       │     │   → yield từng token ra token_queue           │    │
│       │     │   → sentinel None khi hoàn tất                │    │
│       │     └───────────────────┬───────────────────────────┘    │
│       │                         │                                │
│       │     ┌───────────────────▼───────────────────────────┐    │
│       │     │ Node 4: store_memories  (background)          │    │
│       │     │   asyncio.create_task()                       │    │
│       │     │   → Document(user_msg, emotion="neutral")     │    │
│       │     │   → Document(assistant_msg, emotion=...)      │    │
│       │     │   → Chroma.aadd_documents([user_doc, ai_doc]) │    │
│       │     └───────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼  token_queue (asyncio.Queue)                             │
│  Sentence Buffer → SentenceChunk → TTS → AudioChunkPayload       │
│                                                   │              │
└───────────────────────────────────────────────────┼──────────────┘
                                                    │ WebSocket send
┌───────────────────────────────────────────────────▼──────────────┐
│                     BROWSER (Frontend)                           │
│  useWebSocket onmessage → enqueueAudio → Web Audio API → Speaker │
│  chatStore → Avatar emotion lerp                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. LangGraph StateGraph — Trái tim điều phối

File: `backend/app/lc_graph.py`

### 2.1 ChatState (Shared State)

Toàn bộ dữ liệu trao đổi giữa các node được định nghĩa trong một `TypedDict`:

```python
class ChatState(TypedDict):
    user_id: str              # ID người dùng (lấy từ localStorage frontend)
    session_id: str           # ID session hiện tại (UUID per tab mount)
    user_text: str            # Tin nhắn người dùng (raw input)
    memory_context: str | None # Kết quả từ Node 1 (Chroma retrieval)
    system_prompt: str        # Prompt hoàn chỉnh từ Node 2
    response_text: str        # Phản hồi hoàn chỉnh từ Node 3
    emotion: str              # Emotion parsed từ phản hồi
    token_queue: asyncio.Queue # Bridge streaming token → sentence buffer
```

### 2.2 Node 1: `retrieve_memories` — Tìm ký ức liên quan

**File:** `backend/app/memory_store.py:44`

```
Input:  user_text ("Dạo này tôi cũng chẳng khỏe")
        user_id  ("u1")
        ↓
[OllamaEmbeddings.aembed_query(user_text)]
        ↓ vector 768-d
[Chroma.similarity_search(query_vector, k=5, filter={"user_id": "u1"})]
        ↓ 3 docs matched (filtered by user_id)
Output: memory_context:
        "- [sad] user: Tôi mệt vì deadline dự án"
        "- [neutral] assistant: Hãy nghỉ ngơi đi..."
        "- [sad] user: Áp lực công việc quá nhiều"
```

**Cơ chế tìm kiếm:**
- Embedding model: `nomic-embed-text` (local qua Ollama)
- Vector similarity: cosine distance trong không gian 768 chiều
- Filter: Chỉ lấy documents có `metadata.user_id == user_id` → mỗi user có không gian ký ức riêng, không cross-contamination
- Kết quả: Chuỗi text nối bởi `\n`, hoặc `None` nếu không có ký ức nào

**Cấu hình liên quan (`config.py`):**
| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `memory_enabled` | `True` | Bật/tắt toàn bộ RAG pipeline |
| `embedding_model` | `nomic-embed-text` | Model embedding (phải `ollama pull` trước) |
| `memory_retrieval_count` | `5` | Số lượng ký ức truy xuất mỗi lượt |
| `chroma_path` | `./chroma_data` | Thư mục persist vector store |

### 2.3 Node 2: `build_prompt` — Xây dựng system prompt động

**File:** `backend/app/lc_graph.py:28` + `backend/app/persona.py:19`

```
Input:  memory_context (từ Node 1, có thể None)
        ↓
[build_system_prompt(memory_context)]
        ↓
System Prompt = persona_block
              + (RELEVANT MEMORIES:\n{memory_context}  ← nếu có)
              + EMOTION_RULES
        ↓
Output: system_prompt (string hoàn chỉnh)
```

**Cấu trúc prompt template (`lc_chain.py:19`):**
```
{persona}              ← render 1 lần lúc startup (partial)
{memory_context}       ← dynamic per-request từ Node 1
{emotion_rules}        ← cố định (partial)
[HISTORY]              ← LangChain auto-inject từ RunnableWithMessageHistory
{user_input}           ← tin nhắn hiện tại
```

**Kỹ thuật `partial()`**: `persona` và `emotion_rules` được pre-fill một lần lúc startup qua `ChatPromptTemplate.partial()`, giảm số biến phải truyền mỗi lần `astream()`.

### 2.4 Node 3: `generate` — Sinh phản hồi + Streaming

**File:** `backend/app/lc_graph.py:32`

Đây là node phức tạp nhất — kết hợp LLM streaming với bridge `asyncio.Queue`:

```
[ChatOllama(llama3:8b).astream(inputs, config=session_config)]
        │  LangChain tự động inject session history
        │  qua RunnableWithMessageHistory
        ▼
for token in chain.astream(...):
    full_response += token
    await token_queue.put(token)    ← bridge ra orchestrator
        │
        ▼
await token_queue.put(None)         ← sentinel: hết stream
        │
        ▼
emotion, _ = _parse_emotion(full_response)
return {"response_text": full_response, "emotion": emotion.value}
```

**Hai lớp memory hoạt động đồng thời trong node này:**

| Lớp | Cơ chế | Phạm vi | TTL |
|-----|--------|---------|-----|
| **Session Memory** (short-term) | `RunnableWithMessageHistory` tự động lưu/inject `HumanMessage`/`AIMessage` theo `session_id` | 1 tab browser | Tắt tab = mất |
| **Long-term Memory** (RAG) | Chroma vector store với embedding search | Xuyên session, persistent | Vĩnh viễn (đến khi xóa DB) |

> **Quan trọng:** Session memory là in-memory (`dict[str, ChatMessageHistory]`), khi tab đóng là mất. Long-term memory persist ra disk qua ChromaDB, sống qua mọi lần restart.

### 2.5 Node 4: `store_memories` — Lưu ký ức (background)

**File:** `backend/app/memory_middleware.py:11`

```
Input:  user_id, session_id, user_text, response_text, emotion
        ↓
[schedule_persist()]
        ↓  asyncio.create_task() — non-blocking
[store_turn("user", user_text, "neutral")]
[store_turn("assistant", response_text, emotion)]
        ↓
[Chroma.aadd_documents([user_doc, assistant_doc])]
        ↓
Output: {} (không làm thay đổi state)
```

**Document schema trong Chroma:**
```python
Document(
    page_content="[neutral] user: Công việc hôm nay stress quá",
    metadata={
        "user_id": "u1",
        "session_id": "s1",
        "timestamp": 1715000000.0,
        "role": "user"
    }
)
```

**Thiết kế background store:**
- Node 4 không block luồng chính — `asyncio.create_task()` chạy độc lập
- Fail an toàn: nếu Chroma gặp lỗi, chỉ log warning, không crash pipeline
- Mỗi lượt chat lưu 2 documents: 1 của user + 1 của assistant

---

## 3. Graph Compilation — Cách các node kết nối

**File:** `backend/app/lc_graph.py:62`

```python
builder = StateGraph(ChatState)

builder.add_node("retrieve_memories", retrieve_memories_node)
builder.add_node("build_prompt",      build_prompt_node)
builder.add_node("generate",          generate_node)
builder.add_node("store_memories",    store_memories_node)

builder.set_entry_point("retrieve_memories")
builder.add_edge("retrieve_memories", "build_prompt")
builder.add_edge("build_prompt",      "generate")
builder.add_edge("generate",          "store_memories")
builder.add_edge("store_memories",    END)

graph = builder.compile()
```

**Graph topology (linear, không rẽ nhánh):**

```
START → [retrieve_memories] → [build_prompt] → [generate] → [store_memories] → END
```

**Visualization (ASCII):**
```
+-------------------+       +---------------+       +----------+       +-----------------+
| retrieve_memories | ----→ | build_prompt  | ----→ | generate | ----→ | store_memories  |
+-------------------+       +---------------+       +----------+       +-----------------+
```

---

## 4. Streaming Bridge — Cách token đi từ LLM đến TTS

Một thách thức kiến trúc quan trọng: LangGraph chạy đồng bộ (node trả về toàn bộ output), nhưng chúng ta cần streaming từng token để sentence-buffering hoạt động.

**Giải pháp: `asyncio.Queue` làm bridge**

```
┌─ LangGraph Task (asyncio.create_task) ─────────────────┐
│                                                         │
│  generate_node()                                        │
│    async for token in chain.astream(...):               │
│      full += token                                      │
│      await token_queue.put(token)   ←──────┐            │
│    await token_queue.put(None)             │            │
│                                            │  Bridge    │
└────────────────────────────────────────────┼────────────┘
                                             │
┌─ Orchestrator Consumer Loop ───────────────┼────────────┐
│                                            │            │
│  while True:                               │            │
│    token = await token_queue.get()  ←──────┘            │
│    if token is None: break                              │
│    buffer += token                                      │
│    if _should_flush(buffer, char):                      │
│      chunk = _flush_buffer(buffer)                      │
│      await sentence_queue.put(chunk)                    │
│                           │                             │
└───────────────────────────┼─────────────────────────────┘
                            │
                            ▼
                 SentenceChunk → TTS → AudioChunkPayload → WebSocket
```

Chi tiết code: `orchestrator.py:104-115`

---

## 5. LangSmith Observability

### 5.1 Cách bật

Thêm vào `backend/.env`:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key_here
LANGCHAIN_PROJECT=interactive-chatbot
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

**Không cần sửa code** — LangChain tự động detect env vars và gửi traces.

### 5.2 Dashboard view của một lượt chat

```
LangGraph Run: "chat_pipeline"              Total: 1.3s
├── Node: retrieve_memories                  23ms
│   └── OllamaEmbeddings.embed_query()      18ms
│   └── Chroma.similarity_search()           5ms  → 3 docs retrieved
│       ├── "[sad] user: Tôi mệt vì deadline"   score: 0.92
│       ├── "[neutral] assistant: Hãy nghỉ..."   score: 0.87
│       └── "[sad] user: Áp lực quá..."          score: 0.81
│
├── Node: build_prompt                        1ms
│   └── Rendered system prompt:
│       "You are Aria. [PERSONA] [MEMORIES: ...] [EMOTION RULES: ...]"
│
├── Node: generate                         1240ms
│   └── ChatOllama (llama3:8b)
│       Input tokens:  89
│       Output tokens: 43
│       Stream chunks: 18
│       Response: "[sad] Tôi hiểu cảm giác đó..."
│
└── Node: store_memories                      8ms
    └── Chroma.aadd_documents()  ✓  2 docs added
```

### 5.3 Debug với LangSmith

| Vấn đề | Cách debug |
|--------|-----------|
| Memory retrieve sai ngữ cảnh | Xem danh sách docs retrieved + similarity score từng doc |
| Prompt inject không đúng | Xem rendered prompt đầy đủ (bao gồm memories đã inject) |
| Node nào gây latency cao | Xem timeline per node — thường `generate` node chiếm 90%+ |
| LLM trả lời không có emotion tag | Xem raw output trước khi `_parse_emotion()` |
| Graph đi sai nhánh | Xem execution path trên graph view |
| Session history có được inject không | Xem prompt có chứa `[HISTORY]` messages từ các turn trước |

---

## 6. Luồng dữ liệu hoàn chỉnh (End-to-End)

### 6.1 Trước khi user gửi tin nhắn

```
Frontend mount:
  chatStore.userId    ← localStorage.getItem('chat_user_id') || crypto.randomUUID()
                      → Persist qua mọi lần reload/tắt tab
  chatStore.sessionId ← crypto.randomUUID()
                      → Mới mỗi lần mount (mở tab mới = session mới)
```

### 6.2 User gửi "Dạo này stress quá..."

```
[Frontend]
useWebSocket.sendMessage("Dạo này stress quá...")
  → ws.send({ type: "user_message", text, user_id: "u1", session_id: "s4" })

[Backend] main.py:202
  → orchestrator.run(user_text, session_id="s4", user_id="u1", sentence_queue)
  → graph.ainvoke({ user_id: "u1", session_id: "s4", user_text, token_queue })

  [Node 1: retrieve_memories]
    embed("Dạo này stress quá...") → vector
    Chroma.similarity_search(vector, k=5, filter={"user_id": "u1"})
    → Tìm thấy: "[sad] user: Công việc áp lực quá" (score 0.91)
    → memory_context = "- [sad] user: Công việc áp lực quá"

  [Node 2: build_prompt]
    build_system_prompt(memory_context)
    → "You are Aria. I am a warm AI companion.\n
       RELEVANT MEMORIES:\n- [sad] user: Công việc áp lực quá\n\n
       CRITICAL INSTRUCTION — EMOTION TAGS: ..."

  [Node 3: generate]
    chain.astream(inputs, config={"session_id": "s4"})
    → RunnableWithMessageHistory injects history từ turn trước trong session "s4"
    → ChatOllama.astream() → stream từng token
    → await token_queue.put(token) ...

  [Orchestrator Consumer]
    token = await token_queue.get()
    buffer += token → "Tôi" → "Tôi hiểu" → "Tôi hiểu cảm" → ...
    _should_flush? gặp dấu .!? hoặc dấu phẩy + buffer ≥ 15 chars
    → flush: "[sad] Tôi hiểu cảm giác đó,"
    _parse_emotion → Emotion.sad
    → SentenceChunk(text="Tôi hiểu cảm giác đó,", emotion=sad)
    → sentence_queue.put(chunk)

  [main.py Consumer]
    chunk = await sentence_queue.get()
    TTS.synthesize(chunk) → audio_bytes
    AudioChunkPayload(text, emotion, audio_base64, visemes)
    → ws.send(payload.json())

  [Node 4: store_memories] (chạy song song, không block)
    schedule_persist("u1", "s4", "Dạo này stress quá...", "Tôi hiểu cảm giác đó...", "sad")
    → asyncio.create_task()
    → Chroma.aadd_documents([user_doc, assistant_doc])
```

### 6.3 Cross-session: user mở tab mới

```
[Tab mới mount]
  chatStore.userId    ← localStorage.getItem('chat_user_id') → "u1" (giữ nguyên)
  chatStore.sessionId ← crypto.randomUUID() → "s6" (mới)

[User gửi: "Gần đây tôi vẫn hay mệt mỏi"]
  → user_id="u1", session_id="s6"

[Node 1: retrieve_memories]
  embed("Gần đây tôi vẫn hay mệt mỏi") → vector
  Chroma.similarity_search(..., filter={"user_id": "u1"})
  → Tìm thấy ký ức từ SESSION CŨ:
    "- [sad] user: Công việc áp lực quá" (score 0.88)
    "- [sad] user: Dạo này stress quá..." (score 0.85)

[Node 2 & 3]
  Prompt đã có memories cross-session
  LLM: "Có vẻ gần đây bạn đang gặp nhiều căng thẳng. Lần trước bạn
        cũng kể về áp lực công việc..."
  → Avatar NHỚ được context xuyên session ✓
```

---

## 7. Cấu hình hệ thống

### 7.1 Environment Variables

```env
# ── RAG Pipeline ──
MEMORY_ENABLED=true                         # Bật/tắt toàn bộ RAG
CHROMA_PATH=./chroma_data                   # Thư mục persist vector DB
EMBEDDING_MODEL=nomic-embed-text            # Model embedding (cần ollama pull)
MEMORY_RETRIEVAL_COUNT=5                    # Số ký ức truy xuất mỗi lượt

# ── Character Persona ──
CHARACTER_NAME=Aria
CHARACTER_BACKSTORY="I am a warm and empathetic AI companion."
CHARACTER_PERSONALITY="curious, caring, gently playful"

# ── LLM ──
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b

# ── LangSmith (optional) ──
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key_here
LANGCHAIN_PROJECT=interactive-chatbot
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 7.2 Prerequisites

```bash
ollama pull llama3:8b           # LLM model
ollama pull nomic-embed-text    # Embedding model (bắt buộc cho RAG)
```

### 7.3 Volume (Docker)

```yaml
# docker-compose.yml
backend:
  volumes:
    - chroma_data:/app/chroma_data    # Persist long-term memory

volumes:
  chroma_data:
```

---

## 8. File Map — Ai làm gì

| File | Vai trò trong RAG |
|------|-------------------|
| `backend/app/lc_graph.py` | **Orchestrator**: Định nghĩa StateGraph, 4 node, edge connections, `graph = builder.compile()` |
| `backend/app/lc_chain.py` | **LLM chain**: `ChatOllama` + `ChatPromptTemplate` + `RunnableWithMessageHistory` — session memory |
| `backend/app/memory_store.py` | **Vector store**: `OllamaEmbeddings` + `Chroma` — lưu và tìm kiếm ký ức dài hạn |
| `backend/app/memory_middleware.py` | **Helper**: `schedule_persist()` — background task lưu memory không block pipeline |
| `backend/app/persona.py` | **Prompt builder**: `build_persona_block()` + `build_system_prompt()` + `EMOTION_RULES` |
| `backend/app/orchestrator.py` | **Bridge**: Tạo token_queue, gọi `graph.ainvoke()`, consumer sentence buffer |
| `backend/app/main.py` | **Entry**: WebSocket loop, parse `user_id`/`session_id`, khởi tạo orchestrator |
| `backend/app/config.py` | **Settings**: Tất cả biến cấu hình RAG (`memory_enabled`, `chroma_path`, ...) |
| `backend/app/models.py` | **Schema**: `UserMessagePayload` (có `user_id`, `session_id`), `Emotion`, `SentenceChunk` |
| `frontend/src/store/chatStore.ts` | **Client ID**: `userId` (localStorage persist) + `sessionId` (per mount UUID) |
| `frontend/src/hooks/useWebSocket.ts` | **Client bridge**: Đính `user_id`, `session_id` vào mọi payload gửi đi |
| `frontend/src/types/index.ts` | **Client schema**: `UserMessagePayload` với `user_id?`, `session_id?` |

---

## 9. Hai lớp Memory — So sánh

| Thuộc tính | Session Memory | Long-term Memory (RAG) |
|-----------|----------------|------------------------|
| **Framework** | `RunnableWithMessageHistory` | `Chroma` + `OllamaEmbeddings` |
| **Cơ chế** | Lưu `HumanMessage`/`AIMessage` in-memory dict | Embed text → vector → similarity search |
| **Phạm vi** | 1 session (1 tab browser) | Cross-session (persistent trên disk) |
| **TTL** | Mất khi tắt tab | Vĩnh viễn |
| **Dung lượng** | Không giới hạn (RAM) | Không giới hạn (disk) |
| **Truy xuất** | Theo thứ tự thời gian (turn order) | Theo ngữ nghĩa (semantic similarity) |
| **Injection** | Tự động qua `MessagesPlaceholder("history")` | Thủ công qua `memory_context` trong system prompt |
| **Phụ thuộc** | Không cần model embedding | Cần `nomic-embed-text` |

---

## 10. Best Practices & Design Decisions

### 10.1 Tại sao dùng `asyncio.Queue` thay vì LangGraph streaming API?

LangGraph có `astream_events()` nhưng output ở cấp độ node (khi node hoàn thành), không phải ở cấp độ token. Để sentence-buffering hoạt động (flush ngay khi gặp dấu câu), cần streaming từng token — `asyncio.Queue` là bridge tối ưu.

### 10.2 Tại sao `store_memories` là background task?

Ghi ChromaDB có thể mất 5-50ms tùy vào disk I/O. Để node này chạy đồng bộ sẽ cộng latency vào response time. `asyncio.create_task()` cho phép nó chạy độc lập, không ảnh hưởng TTFB.

### 10.3 Tại sao filter `user_id` trong Chroma query?

Không có filter, user A sẽ retrieve được ký ức của user B — vi phạm privacy và gây hallucination. Filter metadata đảm bảo mỗi user chỉ thấy ký ức của chính mình.

### 10.4 Tại sao dùng `partial()` trong prompt template?

`persona` và `emotion_rules` không thay đổi giữa các request. `partial()` pre-render chúng một lần lúc startup, giảm số biến phải truyền trong mỗi `astream()` call, giảm latency không đáng kể nhưng sạch hơn về mặt kiến trúc.

### 10.5 Tại sao lưu CẢ user và assistant message vào Chroma?

Lưu assistant message giúp tương lai retrieve được context đối thoại 2 chiều. Ví dụ: user hỏi "Như tôi đã nói hôm trước", assistant cần nhớ CẢ user đã nói gì VÀ mình đã trả lời gì để trả lời mạch lạc.

---

## 11. Troubleshooting RAG

| Triệu chứng | Nguyên nhân có thể | Debug |
|------------|-------------------|-------|
| Avatar không nhớ gì | `memory_enabled=false` hoặc chưa `ollama pull nomic-embed-text` | Kiểm tra log lúc startup |
| Memory retrieval trả về rỗng | Chưa có ký ức nào được lưu, hoặc `chroma_path` sai | `python -c "from langchain_chroma import Chroma; ...; print(vs._collection.count())"` |
| Retrieval chậm (>100ms) | `nomic-embed-text` chưa được load vào RAM | Gửi 1-2 request để Ollama warmup model |
| Cross-contamination giữa users | Thiếu `filter={"user_id": user_id}` trong similarity search | Kiểm tra `memory_store.py:49` |
| Memory lưu thất bại | ChromaDB lock file hoặc disk full | Xem log: `Memory store failed: ...` |
| Prompt quá dài (context overflow) | Quá nhiều memories được retrieve | Giảm `memory_retrieval_count`, hoặc thêm token limiter ở `build_prompt_node` |

---

*Cập nhật: 2026-05-11 | Tác giả: Claude (Senior AI Engineer)*
