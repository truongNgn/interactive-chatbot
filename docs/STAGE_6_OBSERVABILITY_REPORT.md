# Stage 6 Observability, Evaluation & Reliability Report

Related: [AI Agent Platform Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md), [Stage 5 Metrics](STAGE_5_RETRIEVAL_METRICS.md), [BRAIN.md](../BRAIN.md), [developer_log.md](../developer_log.md).

## Scope

Stage 6 adds local regression tests, deterministic answer-quality eval, and richer trace metrics without changing the WebSocket/frontend contract.

## Runtime Metrics

Feedback events now expose:

| Event | Metrics |
|---|---|
| `agent_selected` | `agent_id`, `selected_model`, `router_enabled`, `character_id` |
| `first_token` | `latency_ms`, `agent_id`, `selected_model` |
| `first_response_chunk` | `latency_ms` |
| `first_audio` | `latency_ms` when TTS returns audio bytes |
| `tool_called` / `tool_failed` | `tool_name`, `agent_id`, `latency_ms`, error, tool metadata |
| `turn_completed` | end-to-end `latency_ms`, `time_to_first_response_ms`, `time_to_first_audio_ms` |
| `guardrail_blocked` | guardrail decision payload |
| `user_rating_submitted` | rating payload |

`backend/app/feedback/traces.py` can summarize events into:

- tool error rate
- guardrail block rate
- rating up/down counts
- average turn latency

## Tests

Pytest coverage added for:

- router model selection
- sentence buffering and emotion parsing
- tool registry success/block behavior
- guardrails
- text-only turn orchestration
- trace summary metrics

## Evals

Retrieval eval remains:

```bash
python scripts/eval_retrieval.py
```

Answer-quality eval added:

```bash
python scripts/eval_answer_quality.py
```

It is deterministic and rule-based, checking golden answers for expected facts/context and forbidden leakage.

## CI-Like Command

```bash
cd backend
python scripts/smoke_stage6.py
```

Equivalent manual sequence:

```bash
cd backend
python -m pytest -q
python scripts/eval_retrieval.py
python scripts/eval_answer_quality.py
```

## Latest Local Result

```text
11 passed
retrieval eval: pass
answer quality eval: pass
stage6_smoke: ok
```

## Known Technical Debt

- Metrics are JSONL/event based, not pushed to a dashboard.
- Answer-quality eval is rule-based and uses static answer cases; no LLM-as-judge yet.
- Live turn integration still depends on an available LLM provider.
