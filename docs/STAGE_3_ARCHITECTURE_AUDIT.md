# Stage 3 Architecture Audit — AgentRegistry & ToolRegistry MVP

Liên quan: [AI Agent Platform Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md), [Stage 2 Audit](STAGE_2_ARCHITECTURE_AUDIT.md), [BRAIN.md](../BRAIN.md), [developer_log.md](../developer_log.md).

## Runtime Flow

```text
Gateway /ws/chat
  -> ChatRequest
  -> TurnOrchestrator.run_turn()
  -> legacy Orchestrator selects AgentRegistry.default
  -> RoleplayChatAgent.stream()
  -> LangGraph
     -> retrieve_memory tool
     -> retrieve_character_context tool
     -> build_prompt
     -> generate
     -> persist_memory tool
  -> TurnOrchestrator speech/lipsync tools
  -> existing WebSocket payloads
```

## New Modules

| Module | Responsibility |
|---|---|
| `backend/app/agents/base.py` | `AgentContext` and `BaseAgent` protocol. |
| `backend/app/agents/registry.py` | Minimal `AgentRegistry`; default agent selection. |
| `backend/app/agents/roleplay_agent.py` | `RoleplayChatAgent`, wrapping the existing LangGraph pipeline. |
| `backend/app/tools/base.py` | `ToolInput`, `ToolResult`, `BaseTool` protocol. |
| `backend/app/tools/registry.py` | Tool registry, structured fallback result, roleplay allowlist. |
| `backend/app/tools/retrieval.py` | Memory and character context retrieval tools. |
| `backend/app/tools/memory.py` | Memory persistence tool. |
| `backend/app/tools/speech.py` | TTS/STT tool wrappers. |
| `backend/app/tools/lipsync.py` | Rhubarb viseme tool wrapper. |

## Compatibility

- Frontend/WebSocket contract is unchanged.
- `TurnOrchestrator` still sends the same `audio_chunk`, `done`, and `error` payloads.
- `legacy.Orchestrator` remains as a compatibility adapter, but it no longer calls `graph.ainvoke()` directly.
- Direct LangGraph invocation now lives inside `RoleplayChatAgent`.

## Tool Fallbacks

- Retrieval tool failure returns `ToolResult(ok=False)` and graph nodes inject empty context.
- TTS tool failure returns empty bytes, preserving text-only payload behavior.
- Rhubarb tool failure returns no visemes via the registry fallback, preserving audio/text payload delivery.
- `roleplay_chat` allowlist currently permits `retrieve_memory`, `retrieve_character_context`, and `persist_memory`.

## Smoke Commands

```bash
cd backend
python scripts/smoke_stage3.py
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

- Agent selection is still simple: one default `roleplay_chat` agent.
- Tool execution events are logged, but there is no Feedback JSONL/event sink yet.
- Tool policy is an allowlist inside `ToolRegistry`; Stage 4 should move policy into guardrails.
