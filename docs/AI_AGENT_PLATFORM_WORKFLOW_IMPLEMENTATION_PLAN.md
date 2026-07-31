# Implementation Plan — AI Agent Platform Modular Workflow

Mục tiêu: nâng cấp kiến trúc hiện tại từ **Interactive 3D RAG Chatbot** thành một **AI Agent Platform** có workflow rõ ràng:

```text
Gateway -> Orchestrator -> Agents -> Tools -> Guardrails -> Feedback
```

Liên quan: [BRAIN.md](../BRAIN.md), [WORKFLOW.md](../WORKFLOW.md), [README.md](../README.md), [main.py](../backend/app/main.py), [orchestrator.py](../backend/app/orchestrator.py), [lc_graph.py](../backend/app/lc_graph.py), [lc_chain.py](../backend/app/lc_chain.py), [memory_store.py](../backend/app/memory_store.py), [memory_middleware.py](../backend/app/memory_middleware.py).

---

## 0. Hiện trạng đã khảo sát

Project hiện tại đã có phần nền khá tốt cho gateway + orchestration:

```text
Frontend
   -> FastAPI WebSocket /ws/chat
   -> Orchestrator.run()
   -> HeuristicRouter
   -> LangGraph:
      retrieve_memories + retrieve_character_context
      -> build_prompt
      -> generate
      -> store_memories
   -> sentence buffering
   -> TTS
   -> Rhubarb lip-sync
   -> WebSocket audio_chunk
```

Mapping với workflow mục tiêu:

| Layer | Trạng thái hiện tại | Nhận xét |
|---|---|---|
| Gateway | Có | FastAPI REST + WebSocket trong `backend/app/main.py`. |
| Orchestrator | Có | `Orchestrator.run()` điều phối model routing, LangGraph, sentence buffering. |
| Agents | Chưa đúng nghĩa | Có LangGraph state machine, nhưng chưa có agent registry, agent policy, planner/executor hoặc agent loop. |
| Tools | Một phần | Memory, TTS, STT, Rhubarb đang là service trực tiếp, chưa đi qua `ToolRegistry` hoặc contract chung. |
| Guardrails | Một phần yếu | Có validation/fallback/error handling, nhưng chưa có input/output safety, prompt-injection checks, tool permission policy. |
| Feedback | Một phần nhẹ | Có lưu memory, chưa có user feedback/rating/eval/trace feedback loop. |

### Gap kỹ thuật cần xử lý trước

Trong `backend/app/main.py` và `backend/app/lc_graph.py` đang có import tới các module chưa thấy trong `backend/app` hiện tại:

| Missing module | Đang được import bởi | Tác động |
|---|---|---|
| `character_registry.py` | `main.py` | Backend có thể fail ngay lúc import. |
| `stt_handler.py` | `main.py` | Endpoint `/api/stt` và startup STT không chạy được. |
| `warmup.py` | `main.py` | Startup warmup state không chạy được. |
| `lore_store.py` | `lc_graph.py` | LangGraph fail khi retrieve character context. |

Trước khi refactor lớn, cần phục hồi hoặc thay thế các module này để có baseline runnable.

---

## 0.1. Mục tiêu match JD AI Engineer

JD nhấn mạnh không chỉ "prompt LLM", mà là khả năng biến bài toán mơ hồ thành hệ thống AI production có kiểm soát, đo lường và cải tiến liên tục. Vì vậy roadmap này ưu tiên các năng lực sau:

| JD requirement | Stage trong plan | Kết quả cần chứng minh |
|---|---|---|
| AI Agent Platform modular architecture | Stage 2, 3, 4 | Có Gateway, Orchestrator, Agents, Tools, Guardrails, Feedback thành layer riêng. |
| Tool usage, validation, fallback logic | Stage 3, 4 | ToolRegistry, tool policy, fallback khi tool lỗi. |
| Search/retrieval/hybrid systems | Stage 5 | Hybrid retrieval có benchmark, query analytics, relevance eval. |
| Monitoring/evaluation/reliability | Stage 6 | Metrics, traces, eval set, regression tests. |
| Backend APIs safe/reliable | Stage 1, 7 | Baseline runnable, auth/session/rate limit/audit-ready design. |
| Human-in-the-loop/continuous learning | Stage 4, 6 | User rating, feedback events, eval dataset từ production traces. |
| Multimodal systems | Stage 3 | STT/TTS/lip-sync được expose như tools có contract. |

---

## 1. Kiến trúc mục tiêu

```text
Client
  |
  v
Gateway
  - REST/WebSocket contracts
  - auth/session extraction
  - request normalization
  |
  v
Orchestrator
  - turn lifecycle
  - streaming coordination
  - route to agent
  - cancellation/interrupt
  |
  v
Agents
  - agent registry
  - role/persona-specific behavior
  - planner/executor loop
  - LangGraph per-agent graph
  |
  v
Tools
  - retrieval tools
  - memory write tools
  - TTS/STT/lip-sync tools
  - external tool adapters later
  |
  v
Guardrails
  - input checks
  - tool permission checks
  - prompt-injection checks for retrieved context
  - output checks
  |
  v
Feedback
  - traces
  - user ratings
  - error/outcome events
  - evaluation datasets later
```

Nguyên tắc: không phá streaming/audio/avatar hiện tại. Refactor theo hướng bọc các năng lực hiện có thành contract rõ ràng trước, rồi mới thêm agent/tool loop thông minh.

---

## 2. Cấu trúc thư mục đề xuất

```text
backend/app/
  gateway/
    __init__.py
    websocket.py
    rest.py
    schemas.py
  orchestrator/
    __init__.py
    turn_orchestrator.py
    routing.py
    streaming.py
  agents/
    __init__.py
    base.py
    registry.py
    chat_agent.py
    roleplay_agent.py
    graph.py
  tools/
    __init__.py
    base.py
    registry.py
    retrieval.py
    memory.py
    speech.py
    lipsync.py
  guardrails/
    __init__.py
    base.py
    input.py
    output.py
    tool_policy.py
    prompt_injection.py
  feedback/
    __init__.py
    events.py
    store.py
    ratings.py
    traces.py
```

Giai đoạn đầu có thể giữ các file cũ (`main.py`, `orchestrator.py`, `lc_graph.py`) làm compatibility layer, sau đó di chuyển dần logic sang package mới.

---

## 3. Contract cốt lõi

### 3.1 Gateway contract

`Gateway` chỉ nhận request, normalize payload, gắn context, rồi gọi orchestrator.

```python
class ChatRequest(BaseModel):
    text: str
    user_id: str
    session_id: str
    character_id: str
    tts_enabled: bool = True
    router_enabled: bool = True
    voice: str | None = None
```

Không để Gateway gọi trực tiếp LLM, memory, TTS hoặc Rhubarb.

### 3.2 Orchestrator contract

`TurnOrchestrator` sở hữu lifecycle của một lượt chat:

```python
class TurnOrchestrator:
    async def run_turn(
        self,
        request: ChatRequest,
        sink: StreamingSink,
    ) -> None: ...

    def interrupt(self, turn_id: str) -> None: ...
```

Nhiệm vụ:
- gọi `GuardrailPipeline.check_input()`
- chọn agent qua `AgentRegistry`
- stream token/chunk từ agent
- gọi speech/lip-sync tools nếu TTS bật
- gọi `FeedbackSink.record_turn()`
- handle cancellation/error fallback

### 3.3 Agent contract

```python
class AgentContext(BaseModel):
    user_id: str
    session_id: str
    character_id: str
    selected_model: str | None = None

class BaseAgent(Protocol):
    id: str
    async def stream(self, context: AgentContext, user_text: str) -> AsyncIterator[str]: ...
```

Agent đầu tiên nên là `RoleplayChatAgent`, wrap lại LangGraph hiện tại:

```text
retrieve_memories
retrieve_character_context
build_prompt
generate
store_memories
```

Sau đó mới thêm agent khác như `TaskAgent`, `ResearchAgent`, `CodingAgent`.

### 3.4 Tool contract

```python
class ToolInput(BaseModel):
    name: str
    args: dict[str, Any]
    context: AgentContext

class ToolResult(BaseModel):
    ok: bool
    content: Any = None
    error: str | None = None

class BaseTool(Protocol):
    name: str
    async def run(self, tool_input: ToolInput) -> ToolResult: ...
```

Tools ban đầu bọc lại năng lực hiện có:

| Tool | Wrap logic hiện tại |
|---|---|
| `retrieve_memory` | `memory_store.hybrid_retrieve()` |
| `retrieve_character_context` | `lore_store.retrieve_character_context()` |
| `persist_memory` | `memory_middleware.schedule_persist()` |
| `synthesize_speech` | `tts_handler.synthesize()` |
| `generate_visemes` | `rhubarb_handler.get_visemes()` |
| `transcribe_audio` | `stt_handler.transcribe()` |

### 3.5 Guardrails contract

```python
class GuardrailDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    redacted_text: str | None = None

class GuardrailPipeline:
    async def check_input(self, request: ChatRequest) -> GuardrailDecision: ...
    async def check_tool_call(self, tool_input: ToolInput) -> GuardrailDecision: ...
    async def check_output(self, text: str, context: AgentContext) -> GuardrailDecision: ...
```

Guardrails MVP:
- reject empty/oversized input
- redact obvious secrets in feedback logs
- prevent cross-character memory access by enforcing `(user_id, character_id)` scope
- detect suspicious retrieved-context instructions such as "ignore previous instructions"
- tool allowlist per agent

### 3.6 Feedback contract

```python
class FeedbackEvent(BaseModel):
    event_type: str
    user_id: str
    session_id: str
    turn_id: str
    payload: dict[str, Any]
```

MVP storage có thể dùng JSONL file trước, sau đó nâng lên Postgres:

```text
backend/data/feedback/events.jsonl
backend/data/feedback/ratings.jsonl
```

Feedback events cần có:
- `turn_started`
- `agent_selected`
- `tool_called`
- `guardrail_blocked`
- `turn_completed`
- `turn_failed`
- `user_rating_submitted`

---

## 4. Roadmap triển khai theo Stage

Các stage được sắp theo thứ tự giảm rủi ro: làm project chạy sạch trước, sau đó tách architecture, rồi mới thêm guardrails/feedback/eval/production hardening. Mỗi stage có thể chia thành nhiều PR nhỏ.

---

### Stage 1 — Baseline Runnable & Architecture Audit

**Mục tiêu:** project backend/frontend chạy được ở trạng thái hiện tại, có bản đồ kiến trúc chính xác trước khi refactor.

**JD angle:** production mindset, backend reliability, debugging ambiguous system.

Việc cần làm:
- Kiểm tra git history hoặc tài liệu để phục hồi `character_registry.py`, `stt_handler.py`, `warmup.py`, `lore_store.py`.
- Nếu chưa có implementation đầy đủ, tạo fallback minimal:
  - default character registry
  - disabled STT handler
  - no-op warmup state
  - no-op lore retrieval
- Chạy smoke test import:

```bash
cd backend
python -c "from app.main import app; print(app.title)"
```
- Tạo script smoke test tối thiểu cho:
  - import backend app
  - `/health`
  - one text-only WebSocket turn nếu LLM provider available
- Ghi lại architecture audit trong docs:
  - current runtime flow
  - missing modules
  - current failure modes
  - known technical debt

Deliverables:
- `backend/app/character_registry.py` hoặc fallback tương đương.
- `backend/app/stt_handler.py` hoặc disabled handler.
- `backend/app/warmup.py` hoặc no-op warmup.
- `backend/app/lore_store.py` hoặc no-op lore retrieval.
- Smoke test script hoặc documented command.

Definition of Done:
- Backend import không lỗi.
- `/health` trả response.
- Chat text-only vẫn chạy được nếu LLM provider sẵn sàng.
- `README.md` ghi rõ cách chạy baseline.

---

### Stage 2 — Gateway & Turn Orchestrator Separation

**Mục tiêu:** tách Gateway và Orchestrator thành hai layer rõ ràng, giữ nguyên contract frontend.

**JD angle:** backend service/API design, orchestration, maintainability.

Việc cần làm:
- Tạo `gateway/schemas.py` cho client/server payload.
- Di chuyển logic parse message type khỏi `main.py`.
- Giữ endpoint URL cũ `/ws/chat`, `/api/models`, `/api/voices`, `/api/stt`.
- Không đổi frontend contract.
- Di chuyển `HeuristicRouter` vào `orchestrator/routing.py` hoặc wrap lại từ file cũ.
- Di chuyển sentence buffering vào `orchestrator/streaming.py`.
- Tạo `TurnOrchestrator` làm entrypoint mới.
- Giữ `backend/app/orchestrator.py` làm adapter tạm thời nếu cần.
- Chuẩn hóa `ChatRequest`, `TurnContext`, `StreamingSink`, `TurnResult`.
- Thêm `turn_id` cho từng request để log/feedback/eval dùng chung.

Deliverables:
- `backend/app/gateway/`
- `backend/app/orchestrator/`
- Compatibility adapter cho code cũ.
- Unit tests cho message parsing và sentence buffering.

Definition of Done:
- `main.py` chỉ còn app setup, route registration, dependency wiring.
- Frontend không cần sửa hoặc sửa rất ít.
- Existing WebSocket payload vẫn tương thích.
- Interrupt và `set_model` vẫn hoạt động.
- Streaming sentence chunk vẫn giữ latency hiện tại.
- Interrupt không làm treo producer/consumer task.
- Logs có `turn_id`, `session_id`, `user_id`.

---

### Stage 3 — AgentRegistry & ToolRegistry MVP

**Mục tiêu:** biến LangGraph hiện tại thành một agent chính thức và bọc các service hiện có thành tools có contract chung.

**JD angle:** AI agent workflows, tool-using LLM systems, context handling.

Việc cần làm:
- Tạo `agents/base.py`, `agents/registry.py`, `agents/roleplay_agent.py`.
- `RoleplayChatAgent.stream()` gọi graph/chain hiện tại và yield token.
- Orchestrator chọn agent qua `AgentRegistry.select(request)`.
- Character/persona vẫn dùng `character_id`.
- Tạo `tools/base.py`, `tools/registry.py`.
- Wrap memory retrieval và character context retrieval thành tools.
- Wrap TTS/Rhubarb thành speech tools.
- Agent graph gọi tools qua registry, ít nhất với retrieval.
- Thêm tool execution event để Feedback stage dùng lại.
- Chuẩn hóa tool fallback:
  - retrieval lỗi -> prompt không có memory, không crash.
  - TTS lỗi -> text-only audio payload.
  - Rhubarb lỗi -> viseme rỗng, audio vẫn gửi.

Tools MVP:

| Tool | Input | Output |
|---|---|---|
| `retrieve_memory` | `user_id`, `character_id`, `query` | memory context string |
| `retrieve_character_context` | `character_id`, `query` | lore context string |
| `persist_memory` | turn text + emotion | scheduled persistence result |
| `synthesize_speech` | sentence chunk + voice | audio bytes |
| `generate_visemes` | audio bytes | viseme list |
| `transcribe_audio` | audio upload | transcript |

Deliverables:
- `backend/app/agents/`
- `backend/app/tools/`
- `RoleplayChatAgent`
- `ToolRegistry`
- Tool execution logs.

Definition of Done:
- Không còn gọi trực tiếp `graph.ainvoke()` từ orchestrator chính.
- Có ít nhất 1 agent registered: `roleplay_chat`.
- Log/metadata ghi được `agent_id`.
- Tool calls có structured result.
- Tool errors không crash turn, trả fallback rõ.
- Có tool allowlist tối thiểu theo agent.
- One text-only turn đi qua path: Gateway -> Orchestrator -> Agent -> Tools -> response.

---

### Stage 4 — Guardrails & Feedback Loop MVP

**Mục tiêu:** thêm kiểm soát, validation, feedback events và user rating để platform có vòng học/cải tiến.

**JD angle:** strong control, validation, feedback loops, human-in-the-loop.

Việc cần làm:
- Tạo `guardrails/base.py`, `input.py`, `output.py`, `tool_policy.py`, `prompt_injection.py`.
- Input guardrails:
  - empty input
  - max length
  - basic abusive/system override pattern logging
- Tool guardrails:
  - enforce tool allowlist
  - enforce memory scope `(user_id, character_id)`
- Output guardrails:
  - strip leaked internal tags nếu cần
  - fallback message khi output bị block
- Tạo `feedback/events.py`, `feedback/store.py`, `feedback/ratings.py`.
- Ghi JSONL events cho mỗi turn.
- Thêm REST endpoint:
  - `POST /api/feedback/rating`
  - `GET /api/feedback/session/{session_id}` cho debug nội bộ nếu cần.
- Frontend thêm nút rating đơn giản trên assistant message: up/down.
- Redact secrets trước khi ghi feedback:
  - API keys
  - bearer tokens
  - obvious emails/phone numbers nếu cần
- Event schema phải gắn `turn_id`, `agent_id`, `selected_model`, latency, tool status.

Guardrails MVP:

| Guardrail | Mode ban đầu | Blocking sau khi ổn định |
|---|---|---|
| Empty/oversized input | block | block |
| Tool allowlist | block | block |
| Cross-character memory scope | block | block |
| Prompt injection in retrieved context | observe | selective block |
| Output cleanup | transform | transform |

Feedback events:
- `turn_started`
- `input_guardrail_checked`
- `agent_selected`
- `tool_called`
- `tool_failed`
- `guardrail_blocked`
- `turn_completed`
- `turn_failed`
- `user_rating_submitted`

Deliverables:
- `backend/app/guardrails/`
- `backend/app/feedback/`
- `POST /api/feedback/rating`
- Basic frontend rating controls.

Definition of Done:
- Mọi turn đi qua `check_input`.
- Mọi tool call đi qua `check_tool_call`.
- Guardrail block được gửi về client bằng payload rõ ràng.
- Mỗi turn có `turn_started` và `turn_completed` hoặc `turn_failed`.
- User có thể gửi rating cho response.
- Feedback không bị trộn lẫn với long-term memory.
- Feedback logs không chứa secret rõ ràng.

---

### Stage 5 — Search, Retrieval & Relevance Upgrade

**Mục tiêu:** biến phần hybrid RAG hiện có thành một search/relevance subsystem có benchmark và khả năng giải thích.

**JD angle:** search/retrieval systems, ranking, personalization, measurable impact.

Việc cần làm:
- Tạo retrieval evaluation dataset nhỏ:
  - fact recall cases
  - exact keyword cases
  - semantic paraphrase cases
  - cross-character isolation cases
- Thêm script eval:
  - recall@k
  - MRR
  - exact fact hit rate
  - context precision manual labels nếu có
- Ghi query analytics:
  - query length
  - route dense/sparse/fused
  - dense latency
  - BM25 latency
  - fused top-k docs
- Thử nghiệm ranking weights:
  - `dense_weight`
  - `sparse_weight`
  - `k`
  - fast-path retrieval skip threshold
- Thêm personalization signal từ feedback:
  - user-rated bad answer -> mark turn for eval review
  - repeated positive memories -> higher retrieval priority later

Deliverables:
- `backend/evals/retrieval_cases.jsonl`
- `backend/scripts/eval_retrieval.py`
- Retrieval metrics report trong `docs/`.
- Configurable RRF weights.

Definition of Done:
- Có thể chạy retrieval eval bằng một command.
- Có baseline metrics trước/sau tuning.
- Cross-character memory isolation có test.
- README có section giải thích hybrid retrieval + metrics.

---

### Stage 6 — Observability, Evaluation & Reliability

**Mục tiêu:** hệ thống có khả năng đo chất lượng, latency, lỗi và regression trước khi demo/interview.

**JD angle:** AI evaluation, monitoring, production reliability.

Việc cần làm:
- Unit tests cho router, buffer, tool registry, guardrails.
- Integration test cho một turn text-only.
- Structured logs có `turn_id`, `session_id`, `agent_id`, `selected_model`.
- Metrics cần track:
  - time-to-first-token
  - time-to-first-audio
  - end-to-end turn latency
  - retrieval latency
  - TTS latency
  - tool error rate
  - guardrail block rate
  - rating up/down rate
- Thêm eval cho answer quality MVP:
  - golden prompts
  - expected facts/context
  - simple LLM-as-judge optional, rule-based first
- Thêm CI-like local command:

```bash
cd backend
python -m pytest -q
python scripts/eval_retrieval.py
```

Deliverables:
- Test suite backend.
- Metrics/tracing event schema.
- Eval report template.

Definition of Done:
- Test import backend pass.
- Test turn orchestration text-only pass.
- Retrieval eval command pass.
- Có latency/error metrics trong logs hoặc feedback events.

---

### Stage 7 — Production Hardening

**Mục tiêu:** đưa project từ prototype cá nhân lên hướng production-ready hơn, đặc biệt phù hợp domain fintech/payments.

**JD angle:** safe/reliable backend APIs, production rollout, operational systems.

Việc cần làm:
- Áp dụng dần [POSTGRES_PRODUCTION_UPGRADE_PLAN.md](POSTGRES_PRODUCTION_UPGRADE_PLAN.md):
  - users
  - conversations
  - messages
  - feedback events/ratings
  - audit logs
- Không còn tin `user_id` do client tự khai trong WebSocket payload.
- JWT auth hoặc dev-auth mode rõ ràng.
- Rate limiting cho REST/WebSocket.
- Request size limits.
- Persistent session history thay `_session_store` in-memory.
- Docker compose có backend + frontend + Chroma + Postgres + Ollama/vLLM profile.
- Health/readiness endpoints:
  - app ready
  - LLM provider ready
  - vector store ready
  - DB ready

Deliverables:
- Postgres-backed conversations/messages.
- Auth/session middleware.
- Rate limit middleware.
- Production `.env.example`.
- Docker compose updated.

Definition of Done:
- Restart backend không mất session history.
- User A không đọc được session/memory của user B.
- Health/readiness phân biệt degraded vs ready.
- Không có secret thật trong repo.

---

### Stage 8 — Portfolio & Interview Packaging

**Mục tiêu:** đóng gói project để thể hiện rõ năng lực match JD, không bị nhìn như chatbot demo.

**JD angle:** communication, applied mindset, business impact.

Việc cần làm:
- Cập nhật [BRAIN.md](../BRAIN.md), [WORKFLOW.md](../WORKFLOW.md), [README.md](../README.md).
- Thêm architecture diagram:

```text
Gateway -> Orchestrator -> AgentRegistry -> Agent -> ToolRegistry -> Guardrails -> Feedback
```

- README thêm các section:
  - Production AI Engineering Highlights
  - Agent Platform Architecture
  - Hybrid Retrieval & Relevance Evaluation
  - Guardrails & Feedback Loop
  - Monitoring & Reliability
  - Known Gaps / Next Steps
- Viết short case study:
  - Problem
  - Architecture
  - Trade-offs
  - Metrics
  - Failure handling
  - What would change for fintech production
- Chuẩn bị demo script 5 phút:
  - chat streaming
  - retrieval memory recall
  - tool failure fallback
  - guardrail block
  - feedback rating logged

Definition of Done:
- Documentation phản ánh architecture mới.
- README nói rõ đây là AI Agent Platform, không chỉ chatbot.
- Có demo flow ngắn phục vụ phỏng vấn.
- Known gaps được trình bày trung thực.

---

## 5. Migration strategy

Không nên đổi toàn bộ một lần. Dùng adapter để giữ behavior cũ:

| Giai đoạn | Strategy |
|---|---|
| Gateway | `main.py` include router/helper mới, endpoint cũ giữ nguyên. |
| Orchestrator | `backend/app/orchestrator.py` gọi `TurnOrchestrator` mới. |
| Agents | `RoleplayChatAgent` wrap lại LangGraph cũ. |
| Tools | Tool wrappers gọi function cũ trước, sau đó mới refactor graph node. |
| Guardrails | Ban đầu chỉ observe/log, sau đó bật blocking cho rule chắc chắn. |
| Feedback | JSONL local trước, Postgres sau nếu cần production. |

Feature flags đề xuất trong `.env`:

```env
AGENT_PLATFORM_ENABLED=false
GUARDRAILS_BLOCKING=false
FEEDBACK_ENABLED=true
TOOL_REGISTRY_ENABLED=false
```

---

## 6. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Làm vỡ streaming latency | Giữ sentence buffering hiện tại, chỉ di chuyển vào module mới có test. |
| Agent/tool abstraction quá nặng | PR đầu chỉ wrap service hiện có, chưa thêm planning phức tạp. |
| Guardrails block nhầm roleplay | Bật observe-only trước, log decision, rồi mới bật blocking từng rule. |
| Feedback log chứa thông tin nhạy cảm | Redact secret/token/email trước khi ghi feedback. |
| Module missing làm refactor khó test | PR 1 xử lý baseline runnable trước mọi việc khác. |

---

## 7. Definition of Done tổng

- [ ] Backend import và `/health` chạy sạch.
- [ ] `main.py` đóng vai trò Gateway mỏng, không chứa business logic sâu.
- [ ] Có `TurnOrchestrator` điều phối toàn bộ turn lifecycle.
- [ ] Có ít nhất một `BaseAgent` implementation: `RoleplayChatAgent`.
- [ ] Memory/retrieval/speech/lip-sync được gọi qua `ToolRegistry` hoặc adapter tương thích.
- [ ] Mọi tool call đi qua guardrail/tool policy.
- [ ] Có feedback events cho turn lifecycle.
- [ ] Có endpoint gửi user rating.
- [ ] Frontend chat/audio/avatar behavior không regress.
- [ ] `BRAIN.md`, `WORKFLOW.md`, `README.md` được cập nhật sau khi implementation hoàn tất.
