# Interactive 3D AI Chatbot — Agentic RAG Companion

An async FastAPI + WebSocket backend orchestrating an LLM pipeline with LangGraph, hybrid (dense + sparse) long-term memory over ChromaDB, sentence-level streaming to TTS, and a React Three Fiber avatar synced via viseme/lip-sync data.

Built as a personal deep-dive into the engineering problems that sit underneath every "AI companion" product: how do you give a model persistent memory without it bleeding across contexts, how do you make a multi-second LLM generation *feel* instant, and how do you keep a RAG pipeline correct as it scales past a single flat vector store.

## Why this project

Most chatbot demos call an LLM API and print the response. This one is an attempt to build the layer *around* the model that a real product needs — retrieval, memory isolation, latency engineering, and a pluggable provider layer — and to document the reasoning behind each decision, not just the code.

| What I had to solve | What it demonstrates |
|---|---|
| Prevent character A's roleplay memories from leaking into character B's context | Multi-tenant data isolation in a vector store — designing metadata schemas and filters, not just calling `similarity_search` |
| A single embedding search missed exact keyword matches (names, jargon) | Hybrid retrieval — combined dense (ChromaDB) + sparse (BM25) search, fused with Reciprocal Rank Fusion, with reasoned relative weighting |
| A 3000-word character backstory doesn't fit well as one embedding, but splitting on fixed length breaks mid-sentence | Two-tier chunking — structure-based (Markdown headings) first, recursive character splitting only for oversized sections, parent/child retrieval so search stays precise but generation gets full context |
| Users perceive "typing…" silence as broken, even though the model is streaming fine | Latency engineering — re-buffering an LLM token stream into sentence-level chunks with an adaptive first-chunk threshold, so audio starts before the full response is generated |
| Coupling business logic to one LLM/TTS vendor makes the system brittle | Provider abstraction — swappable LLM (Ollama / vLLM / DeepSeek) and TTS (ElevenLabs / Coqui XTTS-v2) behind a common interface, plus a heuristic router that downgrades to a cheaper model for simple queries |
| Orchestration logic scattered across callbacks becomes unreadable fast | Explicit state-machine orchestration with LangGraph instead of an implicit prompt chain — the pipeline is a graph you can read, trace, and extend |

## Highlights

- **LangGraph orchestration** — a 4-node state machine (`retrieve_memories → retrieve_character_context → build_prompt → generate → store_memories`) instead of a single linear chain, with independent retrieval nodes fanned out in parallel from `START`.
- **Hybrid RAG memory** — ChromaDB dense retrieval + in-memory BM25 sparse retrieval, fused with Reciprocal Rank Fusion (RRF), scoped per `(user_id, character_id)` so roleplay memories never leak across characters. Global vs. character-scoped facts are stored separately so identity info (name, job) still transfers between characters while character-specific secrets don't.
- **Multi-character roleplay** — each character is defined by a Markdown "brain" document (identity/backstory/personality/relationships/rules), chunked with a two-tier strategy: structure-based (Markdown headings) at the top level, parent/child recursive splitting for oversized sections — searched at the child granularity, generated from the full parent section, with core identity sections always anchored regardless of similarity.
- **Two-tier streaming** — LLM token stream is re-buffered into sentence-level chunks (adaptive threshold: short first chunk for fast time-to-first-audio, longer later chunks for fewer TTS calls) before being piped through TTS, Rhubarb lip-sync, and out to the avatar over WebSocket.
- **Pluggable providers** — LLM (Ollama / vLLM / DeepSeek), TTS (ElevenLabs / Coqui XTTS-v2 / text-only fallback), STT (faster-whisper), with a heuristic router that picks a small/large model per query complexity.

See [docs/CHARACTER_BRAIN_IMPLEMENTATION_PLAN.md](docs/CHARACTER_BRAIN_IMPLEMENTATION_PLAN.md) for the full design writeup behind the multi-character memory/chunking system, including the trade-offs considered and rejected.

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
 ├─ retrieve_memories          (Chroma dense + BM25 sparse → RRF fusion, scoped per user+character)
 ├─ retrieve_character_context (character "brain" doc → parent/child chunk retrieval)
 ├─ build_prompt
 ├─ generate                   (Ollama / vLLM / DeepSeek, streamed)
 └─ store_memories             (fire-and-forget persist)
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

## What's next

Honest gaps, tracked deliberately rather than hidden:

- No automated RAG evaluation yet (no golden-set/RAGAS pipeline) — currently judged manually.
- Sentence-boundary detection for TTS buffering is regex-based and doesn't yet handle decimals/abbreviations correctly.
- Multi-character routing is backend-complete; the frontend character picker UI is the next piece to build.

## Notes

This is an active learning project, not a production system — issues above are next on the list, not blind spots.
