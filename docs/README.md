# Documentation Index

This is the main documentation map for the project. The repository root keeps entrypoints and agent guidelines; detailed design notes live under `docs/`.

## Architecture
- [Project Workflow](architecture/WORKFLOW.md) - End-to-end runtime flow, interrupt handling, emotion parsing, and fallback behavior.
- [RAG Workflow](architecture/RAG_WORKFLOW.md) - LangChain/LangGraph/LangSmith, memory retrieval, and streaming bridge.
- [Stage 1 Architecture Audit](STAGE_1_ARCHITECTURE_AUDIT.md)
- [Stage 2 Architecture Audit](STAGE_2_ARCHITECTURE_AUDIT.md)
- [Stage 3 Architecture Audit](STAGE_3_ARCHITECTURE_AUDIT.md)
- [Stage 4 Guardrails/Feedback Audit](STAGE_4_ARCHITECTURE_AUDIT.md)
- [Stage 5 Retrieval Metrics](STAGE_5_RETRIEVAL_METRICS.md)
- [Stage 6 Observability Report](STAGE_6_OBSERVABILITY_REPORT.md)
- [Stage 7 Production Hardening Report](STAGE_7_PRODUCTION_HARDENING_REPORT.md)

## Guides
- [User Guide](guides/USER_GUIDE.md) - Installation, local/Docker startup, TTS configuration, and troubleshooting.
- [Interview Prep](INTERVIEW_PREP.md) - Notes for explaining the project in interviews.
- [Portfolio Case Study](PORTFOLIO_CASE_STUDY.md) - Interview-ready case study, demo flow, trade-offs, and production next steps.

## Active / Pending Plans
- [AI Agent Platform Workflow Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md) - Implemented through the Stage 8 portfolio packaging pass; full Postgres auth/conversation persistence remains pending.
- [Character Brain Implementation Plan](CHARACTER_BRAIN_IMPLEMENTATION_PLAN.md) - Partially scaffolded with character registry and lore retrieval contracts; full lore ingest/retrieval store remains pending.
- [Postgres Production Upgrade Plan](POSTGRES_PRODUCTION_UPGRADE_PLAN.md) - Users/conversations/messages and frontend auth MVP are implemented; Alembic migrations, refresh tokens, feedback/audit tables, and shared rate limiting remain pending.

## Root Docs
- [README](../README.md)
- [Project Brain](../BRAIN.md)
- [Developer Log](../developer_log.md)
- [Codex Guidelines](../AGENTS.md)
- [Claude Guidelines](../claude.md)
- [Gemini Guidelines](../gemini.md)
