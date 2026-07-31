# Stage 2 Architecture Audit — Gateway & Turn Orchestrator Separation

Liên quan: [AI Agent Platform Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md), [Stage 1 Audit](STAGE_1_ARCHITECTURE_AUDIT.md), [BRAIN.md](../BRAIN.md), [developer_log.md](../developer_log.md).

## Runtime Flow

```text
FastAPI main.py
  -> route registration + app lifespan
  -> /ws/chat delegates to gateway.websocket.websocket_chat
  -> gateway parses existing client payloads into ChatRequest
  -> TurnOrchestrator.run_turn()
     -> legacy Orchestrator.run() sentence producer
     -> TTS producer
     -> Rhubarb/audio payload builder
  -> existing WebSocket payloads
```

## Compatibility

- Endpoint URLs are unchanged: `/ws/chat`, `/api/models`, `/api/voices`, `/api/stt`, `/api/stt/status`, `/api/characters`.
- WebSocket server payloads are unchanged: `connected`, `model_changed`, `clear_queue`, `audio_chunk`, `done`, `error`.
- Existing imports are preserved through `backend/app/orchestrator/__init__.py`:
  - `from app.orchestrator import Orchestrator`
  - `from app.orchestrator import _parse_emotion`

## New Modules

| Module | Responsibility |
|---|---|
| `backend/app/gateway/schemas.py` | Normalize existing WebSocket payloads into `ChatRequest`; attach `turn_id`. |
| `backend/app/gateway/websocket.py` | Own WebSocket connection loop, control messages, provider switching, interrupt handling. |
| `backend/app/orchestrator/turn_orchestrator.py` | Own one turn lifecycle: sentence queue, TTS queue, Rhubarb/audio payload, done/error fallback. |
| `backend/app/orchestrator/streaming.py` | Sentence flush and emotion parsing helpers moved out of gateway/main. |
| `backend/app/orchestrator/routing.py` | Compatibility wrapper around the current heuristic router. |
| `backend/app/orchestrator/legacy.py` | Compatibility sentence producer wrapping current LangGraph behavior. |

## Smoke Commands

```bash
cd backend
python scripts/smoke_stage2.py
python scripts/smoke_baseline.py
```

Live text-only turn remains optional and requires an available LLM provider:

```powershell
cd backend
$env:SMOKE_WS_TURN="1"
python scripts/smoke_baseline.py
```

## Known Technical Debt

- `legacy.Orchestrator` still calls LangGraph directly. Stage 3 should route this through an agent registry.
- TTS/Rhubarb are now inside `TurnOrchestrator`, but not yet wrapped as tools. Stage 3 owns tool contracts.
- `main.py` still owns REST endpoints. A future gateway REST module can move them without changing URLs.
