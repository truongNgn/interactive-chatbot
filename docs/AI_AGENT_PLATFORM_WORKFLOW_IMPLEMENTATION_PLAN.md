# Implementation Plan - AI Agent Platform Modular Workflow

Goal: evolve the current **Interactive 3D RAG Chatbot** into an **AI Agent Platform** with a clear modular workflow:

```text
Gateway -> Orchestrator -> Agents -> Tools -> Guardrails -> Feedback
```

Related: [BRAIN.md](../BRAIN.md), [WORKFLOW.md](architecture/WORKFLOW.md), [README.md](../README.md), [main.py](../backend/app/main.py), [lc_graph.py](../backend/app/lc_graph.py), [lc_chain.py](../backend/app/lc_chain.py), [memory_store.py](../backend/app/memory_store.py), [memory_middleware.py](../backend/app/memory_middleware.py).

## 0. Current Runtime

The current backend already has a usable gateway and orchestration foundation:

```text
Frontend
  -> FastAPI WebSocket /ws/chat
  -> Gateway auth + payload normalization
  -> TurnOrchestrator
  -> Guardrails
  -> AgentRegistry
  -> RoleplayChatAgent
  -> LangGraph
     -> retrieve_memories + retrieve_character_context
     -> build_prompt
     -> generate
     -> store_memories
  -> sentence buffering
  -> TTS / text-only fallback
  -> Rhubarb lip-sync
  -> WebSocket audio_chunk/done/error
  -> Feedback events
```

Layer mapping:

| Layer | Status | Notes |
|---|---|---|
| Gateway | Implemented | FastAPI REST + WebSocket, request normalization, auth context. |
| Orchestrator | Implemented | `TurnOrchestrator` owns turn lifecycle, streaming, TTS/lip-sync coordination. |
| Agents | MVP implemented | `AgentRegistry` and `RoleplayChatAgent` wrap the LangGraph roleplay pipeline. |
| Tools | MVP implemented | `ToolRegistry` wraps retrieval, memory persistence, speech, lip-sync, and STT. |
| Guardrails | MVP implemented | Input/output/tool policy/prompt-injection checks. |
| Feedback | MVP implemented | JSONL events, ratings, traces, and summary metrics. |
| Production hardening | MVP implemented | Auth boundary, request limits, rate limits, file-backed session history, readiness. |

## 0.1. AI Engineer JD Alignment

The roadmap is designed to demonstrate production AI engineering, not only prompt usage.

| JD Requirement | Stage | Evidence |
|---|---|---|
| Modular AI Agent Platform architecture | Stages 2-4 | Gateway, Orchestrator, Agents, Tools, Guardrails, Feedback as separate layers. |
| Tool usage, validation, fallback logic | Stages 3-4 | ToolRegistry, tool policy, fallback behavior for retrieval/TTS/lip-sync. |
| Search/retrieval/hybrid systems | Stage 5 | Hybrid retrieval benchmark, query analytics, RRF tuning config. |
| Monitoring/evaluation/reliability | Stage 6 | Metrics, traces, eval set, regression tests. |
| Safe/reliable backend APIs | Stages 1 and 7 | Baseline smoke tests, auth/session/rate-limit/readiness hardening. |
| Human-in-the-loop feedback | Stages 4 and 6 | Ratings, feedback events, trace summaries. |
| Multimodal systems | Stage 3 | STT/TTS/lip-sync exposed through tool contracts. |

## 1. Target Architecture

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
  - planner/executor loop later
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

Main principle: preserve streaming/audio/avatar behavior while wrapping existing capabilities behind clearer contracts.

## 2. Current Package Map

```text
backend/app/
  gateway/
    schemas.py
    websocket.py
  orchestrator/
    turn_orchestrator.py
    routing.py
    streaming.py
    legacy.py
  agents/
    base.py
    registry.py
    roleplay_agent.py
  tools/
    base.py
    registry.py
    retrieval.py
    memory.py
    speech.py
    lipsync.py
  guardrails/
    base.py
    input.py
    output.py
    tool_policy.py
    prompt_injection.py
  feedback/
    events.py
    store.py
    ratings.py
    traces.py
  auth.py
  rate_limit.py
  session_history.py
```

## 3. Core Contracts

### Gateway

```python
class ChatRequest(BaseModel):
    text: str
    user_id: str
    session_id: str
    character_id: str
    tts_enabled: bool = True
    router_enabled: bool = True
    voice: str | None = None
    turn_id: str
```

The gateway accepts client traffic, resolves auth context, normalizes payloads, and delegates to the orchestrator. It should not call LLM, memory, TTS, or Rhubarb directly.

### Orchestrator

```python
class TurnOrchestrator:
    async def run_turn(self, request: ChatRequest, sink: StreamingSink) -> None: ...
    def interrupt(self) -> None: ...
    def reset(self) -> None: ...
```

Responsibilities:
- run input guardrails
- select agent
- stream chunks/tokens
- call speech/lip-sync tools when TTS is enabled
- record feedback events
- handle cancellation and error fallback

### Agent

```python
class AgentContext(BaseModel):
    user_id: str
    session_id: str
    character_id: str
    agent_id: str | None = None
    selected_model: str | None = None
    turn_id: str | None = None

class BaseAgent(Protocol):
    id: str
    async def stream(self, context: AgentContext, user_text: str) -> AsyncIterator[str]: ...
```

Current agent:
- `roleplay_chat`: wraps the existing LangGraph roleplay pipeline.

Future agents:
- task agent
- research agent
- coding agent
- external-tool agent

### Tool

```python
class ToolInput(BaseModel):
    name: str
    args: dict[str, Any]
    context: AgentContext

class ToolResult(BaseModel):
    ok: bool
    content: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Current tools:

| Tool | Wrapped capability |
|---|---|
| `retrieve_memory` | Hybrid Chroma + BM25 + RRF retrieval. |
| `retrieve_character_context` | Character lore/context retrieval. |
| `persist_memory` | Background memory persistence. |
| `synthesize_speech` | TTS synthesis. |
| `generate_visemes` | Rhubarb lip-sync visemes. |
| `transcribe_audio` | STT transcription. |

### Guardrails

```python
class GuardrailDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    redacted_text: str | None = None
```

MVP behavior:
- block empty or oversized input
- enforce tool allowlist
- enforce user/character memory scope
- observe suspicious prompt-injection patterns in retrieved context
- strip internal tags from output
- redact secrets in feedback logs

### Feedback

Events include:
- `turn_started`
- `input_guardrail_checked`
- `agent_selected`
- `first_token`
- `first_response_chunk`
- `first_audio`
- `tool_called`
- `tool_failed`
- `guardrail_blocked`
- `turn_completed`
- `turn_failed`
- `user_rating_submitted`

## 4. Roadmap By Stage

### Stage 1 - Baseline Runnable And Architecture Audit

Status: Done.

Deliverables:
- fallback `character_registry.py`
- disabled-safe `stt_handler.py`
- no-op/background `warmup.py`
- no-op `lore_store.py`
- baseline smoke script
- architecture audit

Definition of done:
- backend imports cleanly
- `/health` responds
- text-only chat can run when an LLM provider is available

### Stage 2 - Gateway And Turn Orchestrator Separation

Status: Done.

Deliverables:
- `backend/app/gateway/`
- `backend/app/orchestrator/`
- `TurnOrchestrator`
- compatibility adapter for legacy behavior
- tests for message parsing and sentence buffering

Definition of done:
- `main.py` is mostly app setup and route registration
- old WebSocket payloads remain compatible
- interrupt and `set_model` still work
- logs include `turn_id`, `session_id`, `user_id`

### Stage 3 - AgentRegistry And ToolRegistry MVP

Status: Done.

Deliverables:
- `backend/app/agents/`
- `backend/app/tools/`
- `RoleplayChatAgent`
- `ToolRegistry`
- structured tool results and tool execution events

Definition of done:
- text-only turn follows `Gateway -> Orchestrator -> Agent -> Tools -> response`
- tool errors do not crash the turn
- tool allowlist exists per agent

### Stage 4 - Guardrails And Feedback Loop MVP

Status: Done.

Deliverables:
- `backend/app/guardrails/`
- `backend/app/feedback/`
- `POST /api/feedback/rating`
- `GET /api/feedback/session/{session_id}`
- frontend rating controls

Definition of done:
- every turn passes input guardrails
- every tool call passes tool policy
- blocked input returns a clear payload
- every turn records completion or failure
- feedback logs redact obvious secrets

### Stage 5 - Search, Retrieval, And Relevance Upgrade

Status: Done.

Deliverables:
- retrieval eval dataset
- retrieval eval script
- retrieval metrics report
- configurable RRF weights
- query analytics in tool metadata

Definition of done:
- retrieval eval runs by command
- baseline metrics are documented
- cross-character isolation has coverage

### Stage 6 - Observability, Evaluation, And Reliability

Status: Done.

Deliverables:
- backend regression tests
- answer-quality eval dataset/script
- trace summary utilities
- richer latency/error metrics in feedback events

Definition of done:
- backend tests pass
- retrieval eval passes
- answer-quality eval passes
- latency/error metrics are recorded

### Stage 7 - Production Hardening

Status: MVP done on 2026-08-02.

Implemented:
- auth boundary for REST/WebSocket
- backend derives `user_id` from auth/dev context
- REST/WebSocket rate limiting
- request size limits
- file-backed session history replacing purely in-memory history
- Docker Compose includes Postgres
- `/ready` endpoint with degraded/ready semantics

Remaining:
- Alembic migrations for production schema versioning
- Postgres-backed feedback and audit logs
- shared rate limiting for multi-process deployment

Details: [STAGE_7_PRODUCTION_HARDENING_REPORT.md](STAGE_7_PRODUCTION_HARDENING_REPORT.md).

### Stage 8 - Portfolio And Interview Packaging

Status: Done on 2026-08-02.

Delivered:
- README repositioned the project as an AI Agent Platform.
- Workflow and RAG architecture docs updated for the current Stage 7 runtime.
- Portfolio case study added.
- Interview prep rewritten around platform architecture, trade-offs, and demo flow.
- Documentation index updated.
- Production AI engineering highlights, hybrid retrieval, guardrails, feedback, monitoring, reliability, known gaps, and next steps documented.

## 5. Migration Strategy

Use adapters and feature flags instead of rewriting everything at once.

| Area | Strategy |
|---|---|
| Gateway | Keep existing endpoint URLs while delegating to new gateway helpers. |
| Orchestrator | Keep legacy sentence producer as an adapter behind `TurnOrchestrator`. |
| Agents | Wrap LangGraph in `RoleplayChatAgent` first. |
| Tools | Wrap existing services before changing graph internals. |
| Guardrails | Start with clear blocking rules and observe-only prompt-injection checks. |
| Feedback | Keep JSONL local first, then move structured events to Postgres. |
| Production hardening | Use file-backed history as a bridge before full Postgres conversation storage. |

## 6. Risks

| Risk | Mitigation |
|---|---|
| Streaming latency regression | Keep sentence buffering behavior stable and covered by tests. |
| Over-abstracting agent/tool layers | Wrap existing capabilities first; add planning later. |
| Guardrails blocking roleplay incorrectly | Use observe-only mode for ambiguous prompt-injection signals. |
| Feedback logs containing secrets | Redact API keys, bearer tokens, emails, and phone-like strings. |
| Session or memory cross-user leakage | Derive `user_id` from auth and namespace history by `user_id:session_id`. |

## 7. Global Definition Of Done

- [x] Backend import and `/health` work.
- [x] Gateway and turn orchestration are separated.
- [x] `TurnOrchestrator` coordinates turn lifecycle.
- [x] At least one `BaseAgent` implementation exists: `RoleplayChatAgent`.
- [x] Memory/retrieval/speech/lip-sync go through tool wrappers.
- [x] Tool calls pass through guardrail/tool policy.
- [x] Feedback events exist for turn lifecycle.
- [x] User rating endpoint exists.
- [x] Stage 7 MVP prevents trusting client-supplied `user_id`.
- [x] Stage 8 portfolio packaging.
- [x] Full Postgres-backed users/conversations/messages MVP.
- [x] Frontend auth flow MVP.
