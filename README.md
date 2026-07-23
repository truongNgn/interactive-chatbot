# Interactive 3D AI Chatbot — Agentic RAG Companion

An async FastAPI + WebSocket backend orchestrating an LLM pipeline with LangGraph, hybrid (dense + sparse) long-term memory over ChromaDB, sentence-level streaming to TTS, and a React Three Fiber avatar synced via viseme/lip-sync data.

Built as a personal learning project to explore how to give an AI character persistent memory, low-latency streaming responses, and expressive real-time behavior — instead of a static request/response chatbot.

## Highlights

- **LangGraph orchestration** — a 4-node state machine (`retrieve_memories → retrieve_character_context → build_prompt → generate → store_memories`) instead of a single linear chain, with independent retrieval nodes fanned out in parallel.
- **Hybrid RAG memory** — ChromaDB dense retrieval + in-memory BM25 sparse retrieval, fused with Reciprocal Rank Fusion (RRF), scoped per `(user_id, character_id)` so roleplay memories never leak across characters.
- **Multi-character roleplay** — each character is defined by a Markdown "brain" document (identity/backstory/personality/relationships/rules), chunked with a two-tier strategy: structure-based (Markdown headings) at the top level, parent/child recursive splitting for oversized sections — searched at the child granularity, generated from the full parent section.
- **Two-tier streaming** — LLM token stream is re-buffered into sentence-level chunks (adaptive threshold: short first chunk for fast time-to-first-audio, longer later chunks for fewer TTS calls) before being sent to TTS + the 3D avatar.
- **Pluggable providers** — LLM (Ollama / vLLM / DeepSeek), TTS (ElevenLabs / Coqui XTTS-v2 / none), STT (faster-whisper), with a heuristic router that picks a small/large model per query complexity.

See [docs/CHARACTER_BRAIN_IMPLEMENTATION_PLAN.md](docs/CHARACTER_BRAIN_IMPLEMENTATION_PLAN.md) for the design writeup behind the multi-character memory/chunking system.

## Architecture

```
Browser (React Three Fiber avatar)
        │ WebSocket
        ▼
FastAPI /ws/chat
        │
        ▼
Orchestrator ── sentence-buffering ──▶ TTS ──▶ Rhubarb lip-sync ──▶ WebSocket (audio + visemes)
        │
        ▼
LangGraph pipeline
 ├─ retrieve_memories        (Chroma dense + BM25 sparse → RRF fusion)
 ├─ retrieve_character_context (character "brain" doc → parent/child chunk retrieval)
 ├─ build_prompt
 ├─ generate                 (Ollama / vLLM / DeepSeek, streamed)
 └─ store_memories           (fire-and-forget persist)
```

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, WebSockets, asyncio, Pydantic v2 |
| Orchestration | LangChain, LangGraph, LangSmith (optional tracing) |
| Memory / RAG | ChromaDB (dense), BM25 (sparse), Ollama embeddings |
| LLM | Ollama / vLLM (OpenAI-compatible) / DeepSeek |
| TTS | ElevenLabs API / Coqui XTTS-v2 (local voice cloning) |
| STT | faster-whisper |
| Lip-sync | Rhubarb Lip-Sync |
| Frontend | React, React Three Fiber, Three.js, zustand |

## Running locally

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in provider keys/paths as needed
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

Requires [Ollama](https://ollama.com) running locally (or a configured vLLM/DeepSeek endpoint) for the LLM + embedding model.

### Ingesting a character brain document

```bash
cd backend
python -m app.lore_ingest --character luna --file ../docs/characters/luna.md
```

Character metadata (display name, voice, avatar) is registered in [docs/characters/characters.json](docs/characters/characters.json); the frontend can list available characters via `GET /api/characters`.

## Notes

This is an active learning project, not a production system — see the codebase for areas still evolving (RAG eval, richer multi-character UX, etc.).
