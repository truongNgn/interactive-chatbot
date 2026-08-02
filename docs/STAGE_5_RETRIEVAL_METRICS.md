# Stage 5 Retrieval Metrics Report

Related: [AI Agent Platform Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md), [Stage 4 Audit](STAGE_4_ARCHITECTURE_AUDIT.md), [BRAIN.md](../BRAIN.md), [developer_log.md](../developer_log.md).

## Scope

Stage 5 adds a measurable retrieval baseline without changing chat/WebSocket behavior.

Default eval mode is offline and deterministic. It validates:

- exact keyword match through sparse/BM25-style results
- semantic paraphrase through dense-style results
- cross-character isolation by metadata filtering
- fact recall context inclusion

Live retrieval eval is optional because it requires the configured vector store and embedding provider.

## Commands

```bash
cd backend
python scripts/eval_retrieval.py
python scripts/smoke_stage5.py
```

Optional live mode:

```powershell
cd backend
$env:RETRIEVAL_EVAL_LIVE="1"
python scripts/eval_retrieval.py
```

## Current Offline Baseline

```text
cases: 4
recall_at_5: 1.0
mrr: 1.0
forbidden_hit_count: 0
pass: true
```

Cases live in [backend/evals/retrieval_cases.jsonl](../backend/evals/retrieval_cases.jsonl).

## Runtime Retrieval Analytics

`hybrid_retrieve_with_metrics()` now tracks:

- query length
- route (`disabled`, `facts_only`, `empty`, `hybrid`)
- facts/dense/sparse/fused counts
- BM25 store size
- facts/dense/sparse/total latency
- fast-path skip flag
- retrieval errors

Retrieval tools attach these metrics to `ToolResult.metadata`, so Stage 4 feedback events can include them in `tool_called` payloads.

## Config

```env
MEMORY_RRF_K=60
MEMORY_DENSE_WEIGHT=1.0
MEMORY_SPARSE_WEIGHT=1.5
MEMORY_DENSE_OVERFETCH_MULTIPLIER=2
```

## Known Technical Debt

- Offline eval uses synthetic dense/sparse result lists; live eval should be run after Ollama/Chroma are available.
- Metrics are logged and attached to feedback events but not yet aggregated into dashboards.
- Tuning is configurable, but no automated weight sweep is implemented yet.
