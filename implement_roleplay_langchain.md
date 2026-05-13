# Implementation Plan: Character Roleplay + Long-term Memory
## Phiên bản LangChain / LangGraph

> **Mục đích kép:** Implement feature + học cách dùng LangChain/LangGraph đúng cách.
> File này thay thế `implement_roleplay.md` (plain Python version).

---

## ✅ Progress Tracker

### Setup
- [ ] Tạo account LangSmith tại [smith.langchain.com](https://smith.langchain.com)
- [ ] Thêm LangSmith env vars vào `backend/.env`
- [ ] Thêm LangSmith env vars vào `backend/.env.example`
- [ ] Cài dependencies: `pip install langchain langchain-ollama langchain-chroma langgraph langsmith`
- [ ] Cập nhật `backend/requirements.txt`

### Stage 1 — LangChain Core
- [ ] Tạo `backend/app/lc_chain.py`
- [ ] Sửa `backend/app/orchestrator.py` (dùng `chain.astream()`)
- [ ] Sửa `backend/app/models.py` (thêm `user_id`, `session_id`)
- [ ] Sửa `backend/app/main.py` (parse user_id/session_id)
- [ ] Sửa `frontend/src/store/chatStore.ts` (thêm userId, sessionId)
- [ ] Sửa `frontend/src/hooks/useWebSocket.ts` (đính user_id, session_id)
- [ ] Sửa `frontend/src/types/index.ts` (cập nhật UserMessagePayload)
- [ ] Verification: avatar nhớ tên trong cùng session

### Stage 2 — Character Persona
- [ ] Tạo `backend/app/persona.py`
- [ ] Sửa `backend/app/config.py` (thêm character_name, backstory, personality)
- [ ] Sửa `backend/app/lc_chain.py` (thay SYSTEM_PROMPT hardcoded)
- [ ] Sửa `backend/.env.example` (thêm section Character Persona)
- [ ] Verification: avatar có tên + personality riêng

### Stage 3 — LangChain RAG
- [ ] `ollama pull nomic-embed-text`
- [ ] Tạo `backend/app/memory_store.py`
- [ ] Tạo `backend/app/memory_middleware.py`
- [ ] Sửa `backend/app/config.py` (thêm chroma_path, embedding_model, memory_enabled)
- [ ] Sửa `backend/app/main.py` (enrich_with_memory + schedule_persist)
- [ ] Sửa `docker-compose.yml` (volume chroma_data)
- [ ] Verification: avatar nhớ ký ức xuyên session

### Stage 4 — LangGraph Orchestration
- [x] Tạo `backend/app/lc_graph.py`
- [x] Sửa `backend/app/orchestrator.py` (dùng graph.ainvoke())
- [x] Verification: `graph.get_graph().draw_ascii()` hiển thị đúng

---

## 🗺️ Bản đồ Framework

```
LangChain   = Bộ công cụ (LLM, Prompt, Memory, Retriever, Embeddings...)
LangGraph   = Bộ điều phối (ai làm gì, theo thứ tự nào, khi nào rẽ nhánh)
LangSmith   = Kính hiển vi (quan sát mọi thứ xảy ra bên trong chain/graph)
```

**Phép so sánh thực tế:**
- LangChain = các bộ phận cơ khí (động cơ, bánh xe, vô lăng...)
- LangGraph = bản thiết kế chiếc xe (lắp bộ phận nào vào đâu, luồng vận hành thế nào)
- LangSmith = đồng hồ dashboard (theo dõi mọi thông số khi xe chạy)

---

## 🔭 LangSmith — Observability (Setup ngay từ đầu)

> **Tại sao setup trước?** Khi implement từng stage, mở LangSmith dashboard lên xem
> từng bước chạy thế nào — đây là cách học framework hiệu quả nhất.

### Setup (5 phút)

- [ ] **Bước 1 — Tạo account miễn phí:** [smith.langchain.com](https://smith.langchain.com)
  *(Free tier: 5,000 traces/tháng — đủ để dev & học)*

- [ ] **Bước 2 — Thêm vào `backend/.env`:**
```env
# LangSmith Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key_here
LANGCHAIN_PROJECT=interactive-chatbot
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

- [ ] **Bước 3 — Thêm vào `backend/.env.example`:**
```env
# LangSmith Observability (optional — xóa để tắt)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=interactive-chatbot
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

**Không cần sửa code.** LangChain tự động detect env vars và gửi traces.

---

### Bạn thấy gì trên LangSmith Dashboard

Sau khi chat một lượt, mở [smith.langchain.com](https://smith.langchain.com) → project `interactive-chatbot`:

```
LangGraph Run: "chat_pipeline"           Total: 1.3s
├── Node: retrieve_memories              23ms
│   └── OllamaEmbeddings.embed_query()  18ms
│   └── Chroma.similarity_search()       5ms  → 3 docs retrieved
│       ├── "[sad] user: Tôi mệt vì deadline"  score: 0.92
│       ├── "[neutral] assistant: Hãy nghỉ ngơi..." score: 0.87
│       └── "[sad] user: Áp lực quá"    score: 0.81
│
├── Node: build_prompt                    1ms
│   └── Rendered system prompt:
│       "You are Aria. [MEMORIES: ...] [EMOTION RULES: ...]"
│
├── Node: generate                      1240ms
│   └── ChatOllama (llama3:8b)
│       Input tokens:  89
│       Output tokens: 43
│       Stream chunks: 18
│       Response: "[sad] Tôi hiểu cảm giác đó..."
│
└── Node: store_memories                  8ms
    └── Chroma.aadd_documents()  ✓  2 docs added
```

### Những gì LangSmith giúp debug

| Vấn đề | Cách debug với LangSmith |
|---|---|
| Memory retrieve sai | Xem docs retrieved + similarity score |
| Prompt inject không đúng | Xem rendered prompt đầy đủ |
| Node nào gây latency cao | Xem timeline per node |
| LLM trả lời không có emotion tag | Xem raw output trước khi parse |
| Graph đi sai nhánh | Xem execution path trên graph view |

---

## Dependency Chain

```
Stage 1 — LangChain Core: ChatOllama + LCEL + Session Memory
    ├── Stage 2 — Persona: ChatPromptTemplate + dynamic system prompt
    └── Stage 3 — LangChain RAG: OllamaEmbeddings + Chroma + Retriever
                  └── Stage 4 — LangGraph: StateGraph orchestration
```

---

## Kiến trúc tổng thể sau khi hoàn thành

```
WebSocket (main.py)
    │
    ▼
LangGraph StateGraph  ←──────────────────────────────────────────┐
    │                                                              │
    ├─ Node 1: retrieve_memories                                   │
    │   └─ OllamaEmbeddings → Chroma.similarity_search()          │
    │                                                              │
    ├─ Node 2: build_prompt                                        │
    │   └─ ChatPromptTemplate(persona + memories + history)        │
    │                                                              │
    ├─ Node 3: generate_response                                   │
    │   └─ ChatOllama.astream() → sentence buffer → TTS pipeline   │
    │                                                              │
    └─ Node 4: store_memories (background)                         │
        └─ Chroma.aadd_documents()  ───────────────────────────────┘

[TTS + Rhubarb pipeline giữ nguyên — không thay đổi]
```

**LangGraph thay thế:** `orchestrator.py` + `llm_handler.py` (core generation logic)
**Giữ nguyên:** `tts_handler.py`, `rhubarb_handler.py`, `main.py` WebSocket loop

---

## New Dependencies

```txt
# thêm vào backend/requirements.txt
langchain>=0.3.0
langchain-ollama>=0.2.0          # ChatOllama, OllamaEmbeddings
langchain-chroma>=0.1.0          # Chroma vector store
langchain-core>=0.3.0            # LCEL, Runnable, BaseMessage
langgraph>=0.2.0                 # StateGraph
langsmith>=0.1.0                 # Observability (auto-enabled qua env vars)
```

```bash
pip install langchain langchain-ollama langchain-chroma langgraph langsmith
```

---

---

# Stage 1 — LangChain Core: ChatOllama + LCEL + Session Memory

**Goal:** Thay `llm_handler.py` (raw Ollama SDK) bằng LangChain chain.
Avatar có multi-turn memory trong session.

---

## 📚 Concept 1: LCEL — LangChain Expression Language

LCEL là cách "nối" các component lại với nhau bằng toán tử `|` (pipe).

```python
# Pattern cơ bản
chain = prompt | llm | output_parser

# Chạy chain
response = await chain.ainvoke({"user_input": "Hello"})
```

**Tương tự Unix pipe:** `cat file.txt | grep "error" | wc -l`
Mỗi bước nhận output của bước trước → transform → truyền xuống.

---

## 📚 Concept 2: ChatOllama

Wrapper của LangChain cho Ollama. Thay vì gọi `ollama.AsyncClient().chat()` thủ công:

```python
# Trước (raw SDK):
async for part in await client.chat(model=..., messages=..., stream=True):
    yield part["message"]["content"]

# Sau (LangChain):
from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3:8b", base_url="http://localhost:11434")
async for chunk in llm.astream("Hello"):
    print(chunk.content)   # LangChain tự xử lý stream format
```

**Lợi ích:** Swap sang DeepSeek/OpenAI chỉ cần đổi 1 dòng init.

---

## 📚 Concept 3: ChatPromptTemplate

Thay thế hardcoded `messages = [{"role": "system", ...}, {"role": "user", ...}]`:

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),      # dynamic system prompt
    MessagesPlaceholder("history"),      # ← slot cho conversation history
    ("human", "{user_input}"),          # current user message
])
```

`MessagesPlaceholder` là slot tự động inject danh sách message cũ vào đúng vị trí.

---

## 📚 Concept 4: RunnableWithMessageHistory

Tự động lưu + inject conversation history vào chain:

```python
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

# Store lưu history per session (in-memory)
session_store: dict[str, ChatMessageHistory] = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]

# Wrap chain với memory
chain_with_memory = RunnableWithMessageHistory(
    base_chain,
    get_session_history,
    input_messages_key="user_input",
    history_messages_key="history",
)

# Gọi với session_id → tự động load/save history
response = await chain_with_memory.ainvoke(
    {"user_input": "Tôi tên là Minh", "system_prompt": SYSTEM_PROMPT},
    config={"configurable": {"session_id": "s1"}},
)
```

**Key insight:** Không cần tự viết `SessionStore` nữa — LangChain lo hết.

---

## Files thay đổi — Stage 1

- [ ] **Tạo mới: `backend/app/lc_chain.py`**

File trung tâm chứa LangChain chain definition:

```python
"""LangChain chain: ChatOllama + ChatPromptTemplate + session history."""

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from app.config import settings

# 1. LLM
llm = ChatOllama(
    model=settings.ollama_model,
    base_url=settings.ollama_host,
)

# 2. Prompt template (system + history slot + user input)
prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    MessagesPlaceholder("history"),
    ("human", "{user_input}"),
])

# 3. Chain: prompt → llm → parse to string
base_chain = prompt | llm | StrOutputParser()

# 4. In-memory session store
_session_store: dict[str, ChatMessageHistory] = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
    return _session_store[session_id]

# 5. Chain + memory
chain = RunnableWithMessageHistory(
    base_chain,
    get_session_history,
    input_messages_key="user_input",
    history_messages_key="history",
)
```

- [x] **Sửa: `backend/app/orchestrator.py`** — thay `self._llm.stream_tokens()` bằng `chain.astream()`

```python
from app.lc_chain import chain, SYSTEM_PROMPT

async def run(self, user_text: str, session_id: str, sentence_queue):
    config = {"configurable": {"session_id": session_id}}
    inputs = {"user_input": user_text, "system_prompt": SYSTEM_PROMPT}

    async for token in chain.astream(inputs, config=config):
        buffer += token
        if _should_flush(buffer, buffer[-1]):
            ...
```

- [x] **Sửa: `backend/app/models.py`**
```python
class UserMessagePayload(BaseModel):
    type: str = "user_message"
    text: str
    user_id: str | None = None
    session_id: str | None = None
```

- [x] **Sửa: `backend/app/main.py`** — parse `user_id`/`session_id` từ WS message, truyền vào orchestrator.

- [x] **Sửa: `frontend/src/store/chatStore.ts`** — thêm `userId` (localStorage), `sessionId` (per mount UUID).

- [x] **Sửa: `frontend/src/hooks/useWebSocket.ts`** — đính `user_id`, `session_id` vào mọi payload.

- [x] **Sửa: `frontend/src/types/index.ts`**
```typescript
export interface UserMessagePayload {
  type: 'user_message'
  text: string
  user_id?: string
  session_id?: string
}
```

---

## Verification — Stage 1

- [x] Chat lượt 1: `"Tôi tên là Minh"` → session_id `s1`
- [x] Chat lượt 2: `"Bạn còn nhớ tên tôi không?"` → session_id `s1`
- [x] Expected: avatar nhắc lại `"Minh"` (LangChain tự inject history)
- [x] Kiểm tra LangSmith: xem `RunnableWithMessageHistory` đã inject `history` vào prompt chưa

---

---

# Stage 2 — Character Persona: ChatPromptTemplate nâng cao

**Goal:** Avatar có tên, backstory, tính cách — cấu hình qua `.env`.

---

## 📚 Concept 5: PromptTemplate với variables

```python
from langchain_core.prompts import PromptTemplate

persona_template = PromptTemplate.from_template("""
You are {character_name}. {backstory}
Personality: {personality}
Never break character.
""")

# Render thành string
persona_block = persona_template.format(
    character_name="Aria",
    backstory="I am a warm AI companion...",
    personality="curious, caring, playful",
)
```

---

## 📚 Concept 6: Partial prompt — bind biến trước

```python
# Bind character_name cố định, chỉ để memory_context thay đổi per-call
persona_prompt = ChatPromptTemplate.from_messages([
    ("system", "{persona}\n\n{memory_context}\n\n{emotion_rules}"),
    MessagesPlaceholder("history"),
    ("human", "{user_input}"),
]).partial(
    persona=build_persona_block(),       # render 1 lần lúc startup
    emotion_rules=EMOTION_RULES,         # cố định
)
```

`partial()` = pre-fill một số biến → giảm số biến phải truyền mỗi lần invoke.

---

## Files thay đổi — Stage 2

- [x] **Tạo mới: `backend/app/persona.py`**

```python
from app.config import settings

EMOTION_RULES = """
CRITICAL INSTRUCTION — EMOTION TAGS:
For EVERY sentence prepend exactly one: [joy] [sad] [neutral] [thinking] [surprise] [anger]
"""

def build_persona_block() -> str:
    return (
        f"You are {settings.character_name}. "
        f"{settings.character_backstory}\n"
        f"Personality: {settings.character_personality}"
    )

def build_system_prompt(memory_context: str | None = None) -> str:
    parts = [build_persona_block(), EMOTION_RULES]
    if memory_context:
        parts.insert(1, f"\nRELEVANT MEMORIES:\n{memory_context}")
    return "\n\n".join(parts)
```

- [x] **Sửa: `backend/app/config.py`**
```python
character_name: str = "Aria"
character_backstory: str = "I am a warm and empathetic AI companion."
character_personality: str = "curious, caring, gently playful"
```

- [x] **Sửa: `backend/app/lc_chain.py`** — thay `SYSTEM_PROMPT` hardcoded → `persona.build_system_prompt(memory_context)`.

- [x] **Sửa: `backend/.env.example`**
```env
# Character Persona
CHARACTER_NAME=Aria
CHARACTER_BACKSTORY=I am a warm and empathetic AI companion.
CHARACTER_PERSONALITY=curious, caring, gently playful
```

---

## Verification — Stage 2

- [x] Đổi `CHARACTER_NAME=Kokoro` trong `.env`, restart backend
- [x] Chat thử → avatar tự xưng "Kokoro"
- [x] Kiểm tra LangSmith: xem rendered system prompt có persona mới chưa

---

---

# Stage 3 — LangChain RAG: OllamaEmbeddings + Chroma + Retriever

**Goal:** Nhớ xuyên session. Retrieve memories liên quan → inject vào prompt.

---

## 📚 Concept 7: Embeddings

Chuyển text thành vector số để tìm kiếm theo **ngữ nghĩa** (không phải keyword):

```python
from langchain_ollama import OllamaEmbeddings

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434",
)

# Embed một câu
vector = await embeddings.aembed_query("Tôi mệt vì deadline")
# → [0.123, -0.456, 0.789, ...]  (1024 chiều)
```

**Ví dụ intuition:** "Tôi mệt" và "I'm exhausted" có vector GẦN nhau dù khác ngôn ngữ.

---

## 📚 Concept 8: Chroma Vector Store

```python
from langchain_chroma import Chroma

vectorstore = Chroma(
    collection_name="chat_memories",
    embedding_function=embeddings,
    persist_directory="./chroma_data",
)

from langchain_core.documents import Document

doc = Document(
    page_content="[sad] user: Tôi mệt vì deadline dự án",
    metadata={"user_id": "u1", "session_id": "s1", "timestamp": 1715000000.0},
)
await vectorstore.aadd_documents([doc])

results = await vectorstore.asimilarity_search(
    query="Tôi lại kiệt sức rồi",
    k=5,
    filter={"user_id": "u1"},
)
```

---

## 📚 Concept 9: Retriever — abstraction layer trên Vector Store

```python
retriever = vectorstore.as_retriever(
    search_kwargs={"k": 5, "filter": {"user_id": user_id}}
)
docs = await retriever.ainvoke("Tôi lại kiệt sức")
```

**Tại sao cần Retriever thay vì gọi vectorstore trực tiếp?**
→ LangGraph nodes nhận/trả Retriever interface chuẩn → dễ swap (Chroma ↔ Qdrant ↔ FAISS).

---

## Files thay đổi — Stage 3

- [x] **Pull embedding model:** `ollama pull nomic-embed-text`

- [x] **Tạo mới: `backend/app/memory_store.py`**

```python
"""LangChain Chroma memory store."""

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from app.config import settings
import time

embeddings = OllamaEmbeddings(model=settings.embedding_model, base_url=settings.ollama_host)
vectorstore = Chroma(
    collection_name="chat_memories",
    embedding_function=embeddings,
    persist_directory=settings.chroma_path,
)

async def store_turn(user_id, session_id, role, text, emotion) -> None:
    doc = Document(
        page_content=f"[{emotion}] {role}: {text}",
        metadata={"user_id": user_id, "session_id": session_id,
                  "timestamp": time.time(), "role": role},
    )
    try:
        await vectorstore.aadd_documents([doc])
    except Exception as e:
        logger.warning("Memory store failed: %s", e)

async def retrieve_memories(user_id, query, k=5) -> str | None:
    try:
        docs = await vectorstore.asimilarity_search(
            query=query, k=k, filter={"user_id": user_id}
        )
        if not docs:
            return None
        return "\n".join(f"- {doc.page_content}" for doc in docs)
    except Exception:
        return None
```

- [x] **Tạo mới: `backend/app/memory_middleware.py`**

```python
import asyncio
from app.memory_store import retrieve_memories, store_turn

async def enrich_with_memory(user_id, query) -> str | None:
    return await retrieve_memories(user_id, query)

def schedule_persist(user_id, session_id, user_text, assistant_text, emotion) -> None:
    asyncio.create_task(_persist(user_id, session_id, user_text, assistant_text, emotion))

async def _persist(user_id, session_id, user_text, assistant_text, emotion):
    await store_turn(user_id, session_id, "user", user_text, "neutral")
    await store_turn(user_id, session_id, "assistant", assistant_text, emotion)
```

- [x] **Sửa: `backend/app/config.py`**
```python
chroma_path: str = "./chroma_data"
embedding_model: str = "nomic-embed-text"
memory_retrieval_count: int = 5
memory_enabled: bool = True
```

- [x] **Sửa: `backend/app/main.py`**
  - Trước pipeline: `memory_context = await enrich_with_memory(user_id, user_text)`
  - Sau pipeline: `schedule_persist(...)`

- [x] **Sửa: `docker-compose.yml`** — thêm volume `chroma_data:/app/chroma_data`

---

## Verification — Stage 3

- [x] Session 1: `"Tôi mệt vì deadline"` → user_id `u1`
- [x] Đóng tab, mở tab mới (session_id mới)
- [x] Session 2: `"Dạo này tôi cũng chẳng khỏe"` → user_id `u1`
- [x] Expected: avatar nhắc ký ức "deadline" từ session trước
- [x] Kiểm tra DB:
```bash
python -c "
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
emb = OllamaEmbeddings(model='nomic-embed-text')
vs = Chroma(collection_name='chat_memories', embedding_function=emb, persist_directory='./chroma_data')
print(vs._collection.count(), 'memories stored')
"
```
- [x] Kiểm tra LangSmith: xem docs retrieved + similarity score

---

---

# Stage 4 — LangGraph: StateGraph Orchestration

**Goal:** Thay `orchestrator.py` bằng LangGraph graph. Đây là điểm học quan trọng nhất.

---

## 📚 Concept 10: StateGraph — trái tim của LangGraph

LangGraph mô hình hóa pipeline AI như một **đồ thị có hướng** (directed graph):
- **State**: dữ liệu chia sẻ giữa các node (TypedDict)
- **Node**: function nhận State → trả State mới
- **Edge**: kết nối các node, có thể conditional

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class ChatState(TypedDict):
    user_id: str
    session_id: str
    user_text: str
    memory_context: str | None
    system_prompt: str
    response_text: str
    emotion: str
```

---

## 📚 Concept 11: Nodes — functions biến đổi State

```python
async def retrieve_memories_node(state: ChatState) -> dict:
    context = await retrieve_memories(state["user_id"], state["user_text"])
    return {"memory_context": context}

async def build_prompt_node(state: ChatState) -> dict:
    system = build_system_prompt(state["memory_context"])
    return {"system_prompt": system}

async def generate_node(state: ChatState) -> dict:
    full_response = ""
    config = {"configurable": {"session_id": state["session_id"]}}
    async for token in chain.astream(
        {"user_input": state["user_text"], "system_prompt": state["system_prompt"]},
        config=config,
    ):
        full_response += token
    return {"response_text": full_response, "emotion": extract_emotion(full_response)}

async def store_memories_node(state: ChatState) -> dict:
    schedule_persist(state["user_id"], state["session_id"],
                     state["user_text"], state["response_text"], state["emotion"])
    return {}
```

---

## 📚 Concept 12: Compile và chạy Graph

```python
builder = StateGraph(ChatState)
builder.add_node("retrieve_memories", retrieve_memories_node)
builder.add_node("build_prompt", build_prompt_node)
builder.add_node("generate", generate_node)
builder.add_node("store_memories", store_memories_node)

builder.set_entry_point("retrieve_memories")
builder.add_edge("retrieve_memories", "build_prompt")
builder.add_edge("build_prompt", "generate")
builder.add_edge("generate", "store_memories")
builder.add_edge("store_memories", END)

graph = builder.compile()
```

**Visualization:**
```python
from IPython.display import Image
Image(graph.get_graph().draw_mermaid_png())
```

---

## 📚 Concept 13: Streaming token ra ngoài từ LangGraph node

Dùng `asyncio.Queue` làm bridge giữa LangGraph node và sentence-buffer:

```python
class ChatState(TypedDict):
    ...
    token_queue: asyncio.Queue

async def generate_node(state: ChatState) -> dict:
    q = state["token_queue"]
    full_response = ""
    async for token in chain.astream(...):
        full_response += token
        await q.put(token)
    await q.put(None)  # sentinel
    return {"response_text": full_response, ...}
```

```python
# Phía orchestrator (graph runner):
token_queue = asyncio.Queue()
graph_task = asyncio.create_task(graph.ainvoke({..., "token_queue": token_queue}))

while True:
    token = await token_queue.get()
    if token is None:
        break
    buffer += token
    if _should_flush(buffer, buffer[-1]):
        ...
```

---

## Files thay đổi — Stage 4

- [x] **Tạo mới: `backend/app/lc_graph.py`** — State, nodes, edges, `graph = builder.compile()`
- [x] **Sửa: `backend/app/orchestrator.py`** — dùng `graph.ainvoke()` thay vì gọi LLM trực tiếp

---

## Verification — Stage 4

- [x] Visualize graph:
```bash
python -c "
from app.lc_graph import graph
print(graph.get_graph().draw_ascii())
"
```
- [ ] Expected: 4 nodes theo thứ tự `retrieve_memories → build_prompt → generate → store_memories`
- [ ] Kiểm tra LangSmith: xem từng node trong graph timeline

---

## 🧭 Tổng quan: LangChain / LangGraph / LangSmith trong project này

| Vai trò | Component | Thay thế cái gì |
|---|---|---|
| Gọi LLM | `ChatOllama` | `ollama.AsyncClient().chat()` |
| Cấu trúc prompt | `ChatPromptTemplate` | hardcoded `messages = [...]` |
| Session memory | `RunnableWithMessageHistory` | custom `SessionStore` class |
| Embedding | `OllamaEmbeddings` | `ollama.AsyncClient().embeddings()` |
| Vector search | `Chroma` | raw ChromaDB client |
| Pipeline orchestration | `StateGraph` | `Orchestrator` class + `LLMHandler` |
| Typed state | `TypedDict` | (không có equivalent) |
| **Observability** | **`LangSmith`** | **print/logging thủ công** |

---

## 📦 Files tổng kết cần tạo/sửa

| File | Action | Stage | Done |
|---|---|---|---|
| `backend/app/lc_chain.py` | NEW | 1 | - [ ] |
| `backend/app/persona.py` | NEW | 2 | - [ ] |
| `backend/app/memory_store.py` | NEW | 3 | - [ ] |
| `backend/app/memory_middleware.py` | NEW | 3 | - [ ] |
| `backend/app/lc_graph.py` | NEW | 4 | - [ ] |
| `backend/app/orchestrator.py` | MODIFY | 1, 4 | - [ ] |
| `backend/app/main.py` | MODIFY | 1, 3 | - [ ] |
| `backend/app/config.py` | MODIFY | 2, 3 | - [ ] |
| `backend/app/models.py` | MODIFY | 1 | - [ ] |
| `backend/.env.example` | MODIFY | 2, LangSmith | - [ ] |
| `backend/requirements.txt` | MODIFY | 1, LangSmith | - [ ] |
| `docker-compose.yml` | MODIFY | 3 | - [ ] |
| `frontend/src/store/chatStore.ts` | MODIFY | 1 | - [ ] |
| `frontend/src/hooks/useWebSocket.ts` | MODIFY | 1 | - [ ] |
| `frontend/src/types/index.ts` | MODIFY | 1 | - [ ] |

---

*Tạo: 2026-05-11 | Version: LangChain/LangGraph + LangSmith | Agent: Claude (Senior AI Engineer)*
