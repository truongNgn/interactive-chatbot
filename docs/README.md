# Documentation Index

Mục lục tài liệu chính của project. Root chỉ giữ entrypoint và agent guidelines; tài liệu chi tiết nằm trong `docs/` theo nhóm dưới đây.

## Architecture
- [Project Workflow](architecture/WORKFLOW.md) - Luồng runtime end-to-end, interrupt, emotion, fallback.
- [RAG Workflow](architecture/RAG_WORKFLOW.md) - LangChain/LangGraph/LangSmith, memory retrieval, streaming bridge.
- [Stage 1 Architecture Audit](STAGE_1_ARCHITECTURE_AUDIT.md)
- [Stage 2 Architecture Audit](STAGE_2_ARCHITECTURE_AUDIT.md)
- [Stage 3 Architecture Audit](STAGE_3_ARCHITECTURE_AUDIT.md)

## Guides
- [User Guide](guides/USER_GUIDE.md) - Cài đặt, chạy local/Docker, cấu hình TTS, troubleshooting.
- [Interview Prep](INTERVIEW_PREP.md) - Ghi chú giải thích project khi phỏng vấn.

## Active / Pending Plans
- [AI Agent Platform Workflow Plan](AI_AGENT_PLATFORM_WORKFLOW_IMPLEMENTATION_PLAN.md) - Partially implemented through AgentRegistry/ToolRegistry MVP; guardrails, feedback, eval, and production hardening remain pending.
- [Character Brain Implementation Plan](CHARACTER_BRAIN_IMPLEMENTATION_PLAN.md) - Partially scaffolded with character registry and lore retrieval contract; full lore ingest/retrieval store is still pending.
- [Postgres Production Upgrade Plan](POSTGRES_PRODUCTION_UPGRADE_PLAN.md) - Not implemented yet; kept as the current production persistence/auth roadmap.

## Root Docs
- [README](../README.md)
- [Project Brain](../BRAIN.md)
- [Developer Log](../developer_log.md)
- [Codex Guidelines](../AGENTS.md)
- [Claude Guidelines](../claude.md)
- [Gemini Guidelines](../gemini.md)
