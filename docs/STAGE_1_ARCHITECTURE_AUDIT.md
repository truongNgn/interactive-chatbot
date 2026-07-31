# Stage 1 Architecture Audit — Baseline Runnable

Liên quan: [AI Agent Platform Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md), [BRAIN.md](../BRAIN.md), [developer_log.md](../developer_log.md).

## Current Runtime Flow

```text
Frontend
  -> FastAPI WebSocket /ws/chat
  -> Orchestrator.run()
  -> HeuristicRouter (optional)
  -> LangGraph
     -> retrieve_memories
     -> retrieve_character_context
     -> build_prompt
     -> generate
     -> store_memories
  -> sentence buffering
  -> TTS or text-only fallback
  -> Rhubarb if audio exists
  -> WebSocket audio_chunk + done
```

## Restored Baseline Modules

| Module | Stage 1 behavior |
|---|---|
| `backend/app/character_registry.py` | Loads `docs/characters/characters.json` when present; otherwise exposes one default character from settings. |
| `backend/app/stt_handler.py` | Keeps `/api/stt/status` and `/api/stt` importable; returns disabled STT until a concrete adapter is restored. |
| `backend/app/warmup.py` | Runs non-blocking provider warmup when enabled; records `idle/running/complete/timeout/failed/disabled`. |
| `backend/app/lore_store.py` | Returns empty character context so LangGraph remains runnable without character brain storage. |

## Known Failure Modes

- `/health` may return `status=degraded` when Ollama/vLLM/DeepSeek is unavailable. That is acceptable for Stage 1 as long as the app imports and responds.
- Text-only WebSocket smoke requires an LLM provider and embedding path to be available because the existing graph still calls memory retrieval and generation.
- Character brain retrieval is currently a no-op fallback; roleplay still has the short persona anchor from `persona.py`.
- STT is intentionally disabled even if `STT_ENABLED=true` because the full transcription adapter is missing from source.

## Smoke Commands

```bash
cd backend
python -c "from app.main import app; print(app.title)"
python scripts/smoke_baseline.py
```

Optional live text-only turn:

```powershell
cd backend
$env:SMOKE_WS_TURN="1"
python scripts/smoke_baseline.py
```

## Technical Debt

- Restore full character brain ingestion/retrieval (`lore_ingest.py`, `lore_store.py`) or replace it with a new tool-backed retrieval contract in Stage 3.
- Restore concrete STT implementation behind `BaseSTTHandler`.
- Add automated tests around gateway payload parsing and sentence buffering in Stage 2.
