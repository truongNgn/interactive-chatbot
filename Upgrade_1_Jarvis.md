# Upgrade 1 — Jarvis Memory & Routing Integration Plan

**Mục tiêu:** Tích hợp hai cải tiến từ OpenJarvis vào dự án Interactive Chatbot 3D:
- **A. Hybrid Memory (BM25 + Dense RRF Fusion)** — nâng cấp recall của ChromaDB RAG
- **B. HeuristicRouter** — tự động chọn model phù hợp theo độ phức tạp query

**Tham khảo:**
- [BRAIN.md](BRAIN.md) — kiến trúc hiện tại
- [developer_log.md](developer_log.md) — nhật ký tiến độ
- [RAG_workflow.md](RAG_workflow.md) — pipeline RAG hiện tại
- [OpenJarvis Memory Docs](document/OpenJarvis/docs/architecture/memory.md)
- [OpenJarvis Learning Docs](document/OpenJarvis/docs/architecture/learning.md)

---

## Bối cảnh & Vấn đề

### Vấn đề A — Memory Recall kém với keyword cụ thể

Pipeline RAG hiện tại (`memory_store.py`) dùng **ChromaDB semantic/dense search duy nhất**. Dense embedding tốt cho ý nghĩa ngữ nghĩa nhưng kém với:
- Tên riêng ngắn: "Truong", "Alice"
- Số liệu cụ thể: mã sản phẩm, ID, ngày tháng
- Keyword kỹ thuật: tên file, câu lệnh

Giải pháp regex `[FACT]` ở Stage 5 là workaround, không scale được.

**Fix đề xuất:** Thêm BM25 (exact keyword matching) và kết hợp với ChromaDB qua **Reciprocal Rank Fusion (RRF)**:
```
RRF_score(doc) = Σ  weight_i / (k + rank_i)
```

### Vấn đề B — Mọi query đều dùng Llama3:8B

Dù query chỉ là "ừ" hay "xin chào", backend luôn gọi Llama3:8B → latency cao không cần thiết. Qwen2.5:1.5B đã có trong config nhưng chưa được tận dụng.

**Fix đề xuất:** `HeuristicRouter` phân tích query trước khi gửi đến LangGraph, chọn model nhỏ hoặc lớn tùy độ phức tạp.

---

## Stage 1 — Chuẩn bị & Khảo sát ✅ HOÀN THÀNH

> **Mục tiêu:** Hiểu rõ code hiện tại trước khi chỉnh sửa, xác định điểm tích hợp.

### 1.1 Khảo sát Memory Pipeline

- [x] Đọc toàn bộ `backend/app/memory_store.py` — hiểu cách ChromaDB lưu/truy vấn
- [x] Đọc `backend/app/memory_middleware.py` — hiểu flow extract facts → store
- [x] Đọc `backend/app/lc_graph.py` Node `retrieve_memories` — xem context inject vào prompt như thế nào
- [x] Ghi lại: collection name, embedding model đang dùng, top_k mặc định

> **Findings 1.1:**
> - Collection: `chat_memories` (Chroma) — persist tại `./chroma_data`
> - Embedding model: `nomic-embed-text` via `OllamaEmbeddings`
> - top_k mặc định: `k=5` trong `retrieve_memories()`, `k=20` trong `retrieve_facts()`
> - `retrieve_memories()` gọi 2 bước: (1) `retrieve_facts()` luôn fetch ALL facts, (2) semantic search `asimilarity_search()` filter `user_id`, loại trừ `doc_type=fact`
> - `memory_middleware.py`: `schedule_persist()` → `asyncio.create_task(_persist())` (background, không block) → gọi `store_turn()` + `_extract_facts()` + `store_fact()`
> - **Điểm inject BM25:** `store_turn()` và `store_fact()` trong `memory_store.py` — mirror dữ liệu vào BM25 tại đây
> - **Điểm inject RRF:** thay `retrieve_memories()` bằng `hybrid_retrieve()` trong `lc_graph.py:25`

### 1.2 Khảo sát LLM Config

- [x] Đọc `backend/app/config.py` — xác định biến cấu hình Ollama, model names
- [x] Đọc `backend/app/lc_chain.py` — xem ChatOllama được khởi tạo thế nào
- [x] Đọc `backend/app/lc_graph.py` — tìm node `generate` để biết điểm inject model
- [x] Đọc `backend/.env.example` — confirm các env var OLLAMA_MODEL, OLLAMA_SMALL_MODEL
- [x] Kiểm tra Ollama đang có model gì: `ollama list` (ghi nhận tên chính xác của Qwen2.5)

> **Findings 1.2:**
> - `config.py`: chỉ có `ollama_model: str = "llama3:8b"` — **chưa có** `ollama_small_model`
> - `lc_chain.py`: `ChatOllama` được khởi tạo tại module-level như singleton — `llm = ChatOllama(model=settings.ollama_model)`. Chain cũng là module-level singleton `chain = RunnableWithMessageHistory(...)` — **cần refactor** để support dynamic model
> - `lc_graph.py`: Node `generate` dùng `chain` import trực tiếp từ `lc_chain.py` (`from app.lc_chain import chain`) — điểm thay đổi là đây
> - `orchestrator.py`: gọi `graph.ainvoke(...)` — điểm inject router là **trước** `graph.ainvoke`, pass `selected_model` vào state
> - Ollama models hiện có:
>   - `qwen2.5:1.5b` ✅ — small model (986 MB, Q4_K_M)
>   - `qwen2.5:latest` — 7.6B (4.7 GB)
>   - `llama3.1:latest` ✅ — large model (8B, 4.9 GB) — **lưu ý: tên thực là `llama3.1:latest`, không phải `llama3:8b`**
>   - `nomic-embed-text:latest` — embedding model
> - `.env.example`: chưa có `OLLAMA_SMALL_MODEL` — cần thêm

### 1.3 Cài đặt dependency

- [x] Thêm `rank-bm25` vào `backend/requirements.txt`
- [x] Xác nhận `sentence-transformers` đã có (dùng cho embedding BM25 tokenizer) hay chưa
- [x] Test install trong venv: `pip install rank-bm25` — không conflict với package hiện tại

> **Findings 1.3:**
> - `rank-bm25`: **chưa có** trong venv — cần cài
> - `sentence-transformers`: **chưa có** — tuy nhiên **không cần thiết** cho plan này vì BM25 tokenizer chỉ cần whitespace split (không cần embedding riêng, dùng lại `nomic-embed-text` của Ollama đã có cho ChromaDB)
> - `requirements.txt`: thiếu `langchain-community` (đang dùng `ChatMessageHistory` từ đó) — note thêm khi cập nhật

---

## Stage 2 — Implement BM25 Memory Backend ✅ HOÀN THÀNH

> **Mục tiêu:** Tạo BM25 backend độc lập, hoạt động song song với ChromaDB.

### 2.1 Tạo file `backend/app/bm25_store.py`

- [x] Định nghĩa class `BM25Store` với interface tương tự ChromaDB store:
  - `add_document(doc_id, text, metadata)` — thêm document vào index
  - `search(query, top_k) -> List[BM25SearchResult]` — trả về list (doc_id, score, text, metadata)
  - `delete(doc_id)` — xóa document
  - `_rebuild_index()` — build lại BM25 index lazily khi index bị invalidate
- [x] BM25 index lưu **in-memory** (dict `_docs` + `BM25Okapi` object, lazy rebuild)
- [x] Implement tokenizer: `_tokenize()` — lowercase + split whitespace, không cần NLTK
- [x] Định nghĩa dataclass `BM25SearchResult(doc_id, score, text, metadata)`
- [x] Xử lý edge case: query rỗng → `[]`, store rỗng → `[]`, score ≤ 0 bị loại

### 2.2 Tích hợp BM25Store với session memory

- [x] Mirror pattern: `_mirror_to_bm25()` helper trong `memory_store.py`
- [x] Singleton `bm25_store` tại module level trong `bm25_store.py`
- [x] Gọi `_mirror_to_bm25()` trong `store_turn()` và `store_fact()` ngay sau ChromaDB write
- [x] Mirror là **non-fatal** — nếu lỗi chỉ log warning, không ảnh hưởng ChromaDB write

### 2.3 Tạo hàm `bm25_retrieve` / RRF + `hybrid_retrieve()`

- [x] BM25 search với user_id filter và doc_type != "fact" filter
- [x] Verify: query "Truong name" → doc chứa "Truong" rank cao nhất (score 0.91)
- [x] Verify: doc xuất hiện ở cả dense + sparse được RRF boost lên rank 1

> **Gộp với Stage 3** — `_rrf_fusion()` và `hybrid_retrieve()` được implement luôn trong Stage 2 vì logic liên quan chặt chẽ.

---

## Stage 3 — Implement RRF Fusion Layer ✅ HOÀN THÀNH (gộp vào Stage 2)

### 3.1 `_rrf_fusion()` trong `memory_store.py`

- [x] Công thức `score += weight / (k + rank)`, k=60, dense_weight=1.0, sparse_weight=1.5
- [x] Merge bằng `page_content` key — doc xuất hiện ở cả 2 nguồn được cộng điểm
- [x] Sort giảm dần, trả về top_k page_content strings

### 3.2 `hybrid_retrieve()` — entry point mới

- [x] Over-fetch `k*2` từ cả dense lẫn sparse trước khi fuse
- [x] Output format giữ nguyên `str | None` — `lc_graph.py` không cần đổi interface

### 3.3 Cập nhật `lc_graph.py`

- [x] `from app.memory_store import hybrid_retrieve`
- [x] `retrieve_memories_node`: gọi `hybrid_retrieve()` thay vì `retrieve_memories()`

### 3.4 Facts không bị RRF

- [x] `retrieve_facts()` vẫn dùng ChromaDB filter `doc_type=fact` — không qua RRF
- [x] BM25 search lọc `doc_type != "fact"` trước khi fuse

---

## Stage 4 — Implement HeuristicRouter ✅ HOÀN THÀNH

> **Mục tiêu:** Phân tích query trước khi gọi LangGraph, chọn model phù hợp.

### 4.1 Tạo file `backend/app/router.py`

- [x] `RoutingContext` dataclass: query, query_length, has_code, has_math, is_greeting, is_short_reply, urgency
- [x] `RoutingDecision` dataclass: model, reason, routing_context

### 4.2 Implement `build_routing_context(query) -> RoutingContext`

- [x] `has_code`: regex — backtick, Python/JS keywords, language names (python, javascript, sql...), coding-intent words (code, function, algorithm, debug...)
- [x] `has_math`: regex — Vietnamese math keywords + English (integral, equation, calculate...) + math symbols (Σ, ∫, π...)
- [x] `is_greeting`: regex anchor `^` — xin chào, hello, hi, hey, alo...
- [x] `is_short_reply`: `length < 20` AND no code/math
- [x] `urgency`: default 0.5, extendable từ WebSocket payload

### 4.3 Implement `HeuristicRouter.select_model()` — 6 rules

- [x] P1 urgency > 0.8 → small (override tất cả, kể cả has_code)
- [x] P2 greeting/short_reply → small
- [x] P3 has_code → large
- [x] P4 has_math → large
- [x] P5 query_length > 300 → large
- [x] P6 fallback → large
- [x] Log: `[ROUTER] "query..." → model (reason)` via `logger.info`

### 4.4 Cập nhật `config.py` và `.env.example`

- [x] Thêm `ollama_large_model`, `ollama_small_model`, `router_enabled` vào `Settings`
- [x] `ollama_model` giữ nguyên làm legacy alias, trỏ về `llama3.1:latest`
- [x] `.env.example` cập nhật đầy đủ 3 vars mới

### 4.5 Tích hợp Router vào `orchestrator.py`

- [x] Router khởi tạo inline trong `run()` — không phải singleton để tránh stale config
- [x] `selected_model = decision.model` khi `router_enabled=True`, else `None`
- [x] Pass `selected_model` vào `graph.ainvoke()` state

### 4.6 Cập nhật `lc_chain.py` và `lc_graph.py`

- [x] `build_chain(model)`: factory với `_chain_cache` per model — tránh tạo lại `ChatOllama` mỗi request
- [x] `chain` singleton backward-compatible vẫn còn (import trực tiếp vẫn hoạt động)
- [x] `ChatState` thêm field `selected_model: str | None`
- [x] Node `generate` gọi `build_chain(state.get("selected_model"))` thay vì dùng global `chain`

> **Test results (10/10 pass):**
> - greeting/short_reply → `qwen2.5:1.5b` ✅
> - urgency=0.9 override has_code → `qwen2.5:1.5b` ✅
> - has_code (python, function keyword) → `llama3.1:latest` ✅
> - has_math (integral, equation) → `llama3.1:latest` ✅
> - fallback → `llama3.1:latest` ✅

---

## Stage 5 — Testing & Validation ✅ HOÀN THÀNH

> **Mục tiêu:** Xác nhận tính năng hoạt động đúng, không regression.

### 5.1 Test Hybrid Memory

- [x] Test case 1 — Tên riêng: BM25 query "Minh ten" → doc chứa "Minh" score 0.91 rank 1
- [x] Test case 2 — Keyword kỹ thuật: "ky su phan mem" → doc chính xác score 3.66 rank 1
- [x] Test case 3 — user_id filter: query "Minh" chỉ trả về doc của đúng user, không lẫn user khác
- [x] Test case 4 — Empty BM25 store → `[]` không crash
- [x] RRF: doc xuất hiện ở cả dense + sparse được boost vào top 2; sparse-only rank trên dense-only

### 5.2 Test HeuristicRouter

- [x] "xin chao" → `qwen2.5:1.5b` (short_reply) ✅
- [x] "ok duoc roi" → `qwen2.5:1.5b` (short_reply) ✅
- [x] "hello" → `qwen2.5:1.5b` (greeting) ✅
- [x] "viet ham python de sap xep mang" → `llama3.1:latest` (has_code) ✅
- [x] "ban co the giai thich khai niem deep learning" → `llama3.1:latest` (fallback) ✅
- [x] urgency=0.9 + has_code → `qwen2.5:1.5b` (urgency override) ✅
- [x] Log format: `[ROUTER] "query..." → model (reason)` xuất hiện đúng trên console

### 5.3 Test tích hợp end-to-end

- [x] Server khởi động sạch — `/health` trả về `{"status":"ok"}`
- [x] WebSocket greeting "xin chao" → response text đầy đủ, không crash
- [x] WebSocket question → response text đầy đủ, TTS disabled mode hoạt động
- [x] All imports không lỗi, `ChatState` có đủ field `selected_model`
- [x] `build_chain` cache: cùng model name trả về cùng object, khác model trả về object khác

---

## Stage 6 — Cleanup & Documentation ✅ HOÀN THÀNH

### 6.1 Code cleanup

- [x] Không có log debug tạm — BM25 dùng `logger.debug`, Router dùng `logger.info` (hợp lý, luôn show)
- [x] Không có import thừa, unused variable
- [x] Type hints đầy đủ: `router.py`, `bm25_store.py`, `memory_store.py`

### 6.2 Cập nhật tài liệu

- [x] `BRAIN.md` — cập nhật file tree, mô tả module, bảng stage status, thêm section Upgrade 1
- [x] `developer_log.md` — xóa log cũ, viết log Upgrade 1
- [x] `backend/.env.example` — đã cập nhật ở Stage 4

### 6.3 Cập nhật `requirements.txt`

- [x] `rank-bm25>=0.2.2` đã thêm ở Stage 2

---

## Tóm tắt file sẽ được tạo mới / chỉnh sửa

| File | Thao tác | Nội dung thay đổi |
|---|---|---|
| `backend/app/bm25_store.py` | **Tạo mới** | BM25Store class, tokenizer, search |
| `backend/app/router.py` | **Tạo mới** | RoutingContext, RoutingDecision, HeuristicRouter |
| `backend/app/memory_store.py` | **Chỉnh sửa** | Thêm BM25 mirror write, `hybrid_retrieve()`, `rrf_fusion()` |
| `backend/app/lc_graph.py` | **Chỉnh sửa** | Node `retrieve_memories` → `hybrid_retrieve`, Node `generate` nhận dynamic model |
| `backend/app/lc_chain.py` | **Chỉnh sửa** | `build_chain()` nhận tham số `model` optional |
| `backend/app/orchestrator.py` | **Chỉnh sửa** | Inject router trước khi gọi lc_graph |
| `backend/app/config.py` | **Chỉnh sửa** | Thêm `ollama_large_model`, `ollama_small_model`, `router_enabled` |
| `backend/.env.example` | **Chỉnh sửa** | Thêm 3 env vars mới |
| `backend/requirements.txt` | **Chỉnh sửa** | Thêm `rank-bm25` |
| `BRAIN.md` | **Chỉnh sửa** | Cập nhật architecture, file tree, stage status |
| `developer_log.md` | **Chỉnh sửa** | Log Upgrade 1 |

---

## Dependency giữa các Stage

```
Stage 1 (Khảo sát)
  │
  ├──► Stage 2 (BM25 Backend) ──► Stage 3 (RRF Fusion) ──┐
  │                                                         ├──► Stage 5 (Testing)
  └──► Stage 4 (HeuristicRouter) ───────────────────────────┘
                                                              │
                                                              └──► Stage 6 (Cleanup)
```

Stage 2 và Stage 4 có thể thực hiện **song song** sau khi Stage 1 hoàn thành.

---

*Kế hoạch tạo ngày: 2026-05-12*
*Dự kiến thực hiện: sau khi confirm với user*
