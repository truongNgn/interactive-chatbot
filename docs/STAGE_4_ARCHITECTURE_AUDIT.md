# Stage 4 Architecture Audit — Guardrails & Feedback MVP

Liên quan: [AI Agent Platform Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md), [Stage 3 Audit](STAGE_3_ARCHITECTURE_AUDIT.md), [BRAIN.md](../BRAIN.md), [developer_log.md](../developer_log.md).

## Runtime Flow

```text
Gateway /ws/chat
  -> ChatRequest(turn_id)
  -> TurnOrchestrator
     -> turn_started event
     -> input guardrail
     -> AgentRegistry -> RoleplayChatAgent
     -> ToolRegistry
        -> tool policy guardrail
        -> tool_called/tool_failed events
     -> output cleanup guardrail
     -> audio_chunk/done payloads
     -> turn_completed or turn_failed event

Frontend assistant message
  -> optional turn_id from audio_chunk
  -> ▲/▼ rating buttons
  -> POST /api/feedback/rating
  -> user_rating_submitted event
```

## New Modules

| Module | Responsibility |
|---|---|
| `backend/app/guardrails/base.py` | `GuardrailDecision`, `GuardrailPipeline`. |
| `backend/app/guardrails/input.py` | Empty/oversized blocking and suspicious input observe mode. |
| `backend/app/guardrails/output.py` | Strip internal XML-like tags from outgoing text. |
| `backend/app/guardrails/tool_policy.py` | Agent tool allowlist and `(user_id, character_id)` scope checks. |
| `backend/app/guardrails/prompt_injection.py` | Observe suspicious retrieved-context instructions. |
| `backend/app/feedback/events.py` | Feedback event schema. |
| `backend/app/feedback/ratings.py` | Rating request schema. |
| `backend/app/feedback/store.py` | Redacted JSONL event/rating store. |

## Compatibility

- WebSocket endpoint and message types are unchanged.
- `audio_chunk` now includes optional `turn_id`; existing clients can ignore it.
- Rating uses REST only: `POST /api/feedback/rating`.
- Debug event read endpoint: `GET /api/feedback/session/{session_id}`.

## Feedback Files

Runtime JSONL files are written under:

```text
backend/data/feedback/events.jsonl
backend/data/feedback/ratings.jsonl
```

These files are ignored by Git.

## Smoke Commands

```bash
cd backend
python scripts/smoke_stage4.py
python scripts/smoke_stage3.py
python scripts/smoke_stage2.py
python scripts/smoke_baseline.py
```

Frontend build command:

```bash
cd frontend
npm run build
```

Current frontend build blocker: `frontend/src/hooks/useSpeechInput.ts` is missing in this checkout.

## Known Technical Debt

- Guardrail policy is minimal and mostly rule-based.
- Prompt-injection checks for retrieved context are observe-only.
- Feedback storage is JSONL; Stage 7 should move this to Postgres.
- Frontend rating is optimistic and logs failed submissions to console.
