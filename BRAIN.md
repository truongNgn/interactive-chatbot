# Project Brain - Interactive 3D Chatbot

Chào Agent, đây là "bộ não" của dự án. File này chứa đựng cấu trúc tổng thể, trạng thái hiện tại và các kiến thức quan trọng để bạn nắm bắt dự án nhanh nhất.

## 🔗 Liên kết nhanh (Agent Guidelines)
- [Gemini Guidelines](gemini.md) - Hướng dẫn cho Gemini Agent.
- [Claude Guidelines](claude.md) - Hướng dẫn cho Claude Agent.
- [Developer Log](developer_log.md) - Nhật ký thay đổi và task hiện tại.
- [RAG Workflow](RAG_workflow.md) - Tài liệu chi tiết về pipeline RAG (LangChain/LangGraph/LangSmith).
- [Claude Simulator Plan](implement_claude_simulator.md) - Plan UI redesign theo style Claude Code.

## 🏗️ Cấu trúc dự án (Current Architecture)

### 1. Backend (FastAPI)
- **Công nghệ:** Python 3.12, FastAPI, Ollama (Llama 3:8b, Qwen 2.5:1.5B), ElevenLabs SDK 1.50.3, Coqui TTS (XTTS-v2, optional).
- **Nhiệm vụ:** Xử lý logic LLM, sentence-buffering, TTS, stream qua WebSocket.
- **venv:** `backend/venv/` — activate bằng `venv/Scripts/activate` (Windows).

### 2. Frontend (React + Three Fiber)
- **Công nghệ:** React 18, Vite 5, TypeScript, R3F v8, Drei v9, Zustand v4, **@dnd-kit** (Drag and Drop).
- **Avatar:** Dynamic models từ thư mục `/models/` — mặc định `fashion_girl_asian_girl.glb`. R3F render 3D character và load animation bằng `useAnimations` hoặc procedural.
- **Nhiệm vụ:** Hiển thị 3D avatar bên phải, audio queue, lip-sync, VAD auto-interrupt, hỗ trợ chọn Model và Voice linh hoạt.
- **UI Layout:** 3 cột (Flex-row): Sidebar (trái) + ChatInterface (giữa) + RightSidebar (phải chứa 3D Scene và dropdowns).
- **Tính năng Sidebar:** Quản lý Project (thư mục), kéo thả Session vào Project, đổi tên Session/Project linh hoạt.

### 3. Deployment (Docker)
- **docker-compose.yml** — 3 services: `frontend` (Nginx), `backend` (FastAPI), `ollama`
- Volume `ollama_data` giữ model qua các lần restart.

### 📁 Sơ đồ thư mục (File Tree)
```
interactive-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, WebSocket /ws/chat, /health
│   │   ├── orchestrator.py   # Token streaming → HeuristicRouter → lc_graph
│   │   ├── router.py         # HeuristicRouter: phân tích query → chọn model (Upgrade 1)
│   │   ├── lc_graph.py       # LangGraph StateGraph: retrieve→prompt→generate→store
│   │   ├── lc_chain.py       # build_chain(model): ChatOllama factory, cache per model
│   │   ├── memory_store.py   # Hybrid retrieval: ChromaDB dense + BM25 sparse + RRF
│   │   ├── bm25_store.py     # BM25Store: in-memory sparse index (Upgrade 1)
│   │   ├── memory_middleware.py # Helper functions xử lý enrich/persist + fact extraction
│   │   ├── persona.py        # Quản lý prompt, character personality/emotion rules
│   │   ├── llm_handler.py    # (Cũ) Ollama Llama 3 — async stream
│   │   ├── tts_handler.py    # ElevenLabs / Coqui XTTS-v2 / NoOp — factory pattern
│   │   ├── models.py         # Pydantic: Emotion, SentenceChunk, AudioChunkPayload, ...
│   │   └── config.py         # pydantic-settings (.env): ollama, elevenlabs, chroma, router...
│   ├── venv/                 # Python virtual environment
│   ├── Dockerfile
│   ├── run.py                # Entry point: uvicorn --reload
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Avatar.tsx        # GLB loader, consume currentModel state, traverse morph mesh
│   │   │   ├── Scene.tsx         # R3F Canvas, PBR lighting
│   │   │   ├── ChatInterface.tsx # Message list + input bar
│   │   │   ├── Sidebar.tsx       # Cột trái: sessions, TTS toggle, LLM select
│   │   │   └── RightSidebar.tsx  # Cột phải: chứa <Scene /> và Dropdown chọn Model/Voice
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts   # WS connect + auto-reconnect (3s) + message routing
│   │   │   ├── useAudioQueue.ts  # Web Audio API sequential playback, text-only mode support
│   │   │   └── useVAD.ts         # Voice Activity Detection (RMS, AnalyserNode) → auto-interrupt
│   │   ├── store/
│   │   │   └── chatStore.ts      # Zustand: sessions[], activeSessionId, ttsEnabled, messages, ...
│   │   ├── types/
│   │   │   ├── index.ts          # WS payload types: Session, AudioChunkPayload, VisemeKeyframe, ...
│   │   │   └── visemeMapping.ts  # Rhubarb phoneme (A-X) → ARKit blendshape weights
│   │   ├── App.tsx               # Root: useWebSocket + useAudioQueue + useVAD (single instance)
│   │   └── main.tsx
│   ├── public/models/
│   │   └── avatar.glb            # Three.js facecap sample (332KB, 52 ARKit blendshapes)
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docker-compose.yml
├── gemini.md
├── claude.md
├── BRAIN.md
├── developer_log.md
├── WORKFLOW.md
├── GUIDE.md
├── implementation_plan.md
└── implement_claude_simulator.md  # Plan UI redesign Claude Code style
```

## ✅ Trạng thái các Stage

| Stage | Tên | Trạng thái |
|-------|-----|-----------|
| 1 | AI Core & Token Streaming (FastAPI + Ollama + WebSocket) | ✅ Hoàn thành |
| 2 | TTS Integration (ElevenLabs + Coqui XTTS-v2 voice cloning + emotion mapping) | ✅ Hoàn thành |
| 3 | 3D Frontend (R3F + Avatar + AudioQueue) — **Tier 3 facecap** | ✅ Hoàn thành |
| 4 | Lip-sync & Emotion Blendshapes (Rhubarb → ARKit) | ✅ Hoàn thành (amplitude fallback + shape keys via Blender) |
| 5 | Interruption (VAD) + Docker | ✅ Hoàn thành |

### 🖥️ UI Simulator (Claude Code Style)
| Stage | Tên | Trạng thái |
|-------|-----|-----------|
| 1 | Session Management — Zustand sessions[], localStorage, createNewSession/switchSession | ✅ Hoàn thành |
| 2 | Sidebar Component — dark navy, New Chat, recent sessions, inline delete confirm | ✅ Hoàn thành |
| 3 | TTS Toggle — backend skip ElevenLabs, frontend text-only mode | ✅ Hoàn thành |
| 4 | Layout Refactor — App.tsx flex row, 3 cột: Left, Center, Right | ✅ Hoàn thành |
| 5 | Dynamic Model/Voice Selection — /api/voices, /api/models, RightSidebar Hot-swap | ✅ Hoàn thành |
| 6 | Project Management — Folders, DND session into project, Inline Rename | ✅ Hoàn thành |

### 🧠 LangChain Migration (Roleplay & Memory)
| Stage | Tên | Trạng thái |
|-------|-----|-----------|
| 1 | LangChain Core (ChatOllama + In-memory Session) | ✅ Hoàn thành |
| 2 | Character Persona (Dynamic Prompting qua `.env`) | ✅ Hoàn thành |
| 3 | Long-term Memory (ChromaDB Vector RAG) | ✅ Hoàn thành |
| 4 | LangGraph (Orchestration Agent Workflow) | ✅ Hoàn thành |
| 5 | Fact Extraction Memory (Regex → Structured Facts) | ✅ Hoàn thành |

### 🚀 Upgrade 1 — Jarvis Memory & Routing (từ OpenJarvis)
| Feature | Mô tả | Trạng thái |
|---------|-------|-----------|
| A | Hybrid Memory: BM25 sparse + ChromaDB dense + RRF Fusion | ✅ Hoàn thành |
| B | HeuristicRouter: auto-route query → llama3.1:latest / qwen2.5:1.5b | ✅ Hoàn thành |

## 🔀 Hybrid Memory & Routing Architecture (Upgrade 1)

### Memory Pipeline (mới)
```
User query
  → hybrid_retrieve(user_id, query)
       ├── retrieve_facts()          → ChromaDB filter doc_type=fact (always inject)
       ├── ChromaDB asimilarity_search(k*2)  → dense results
       ├── BM25Store.search(k*2)             → sparse results (filter user_id)
       └── _rrf_fusion(dense, sparse)        → RRF ranked top-k strings
  → memory_context inject vào system prompt
```

**BM25Store** (`bm25_store.py`): in-memory, thread-safe, lazy index rebuild. Mirror từ `store_turn()` và `store_fact()` trong `memory_store.py`. Mất khi restart server (cold-start: BM25 rỗng, chỉ ChromaDB hoạt động).

**RRF weights**: `sparse_weight=1.5 > dense_weight=1.0` — BM25 bonus là marginal gain cho exact keyword match, dense đã xử lý semantic tốt.

### Routing Pipeline (mới)
```
orchestrator.py
  → HeuristicRouter.select_model(build_routing_context(user_text))
       ├── urgency > 0.8           → qwen2.5:1.5b  (speed override)
       ├── greeting / short < 20c → qwen2.5:1.5b  (trivial queries)
       ├── has_code                → llama3.1:latest
       ├── has_math                → llama3.1:latest
       ├── query_length > 300      → llama3.1:latest
       └── fallback                → llama3.1:latest
  → selected_model truyền vào ChatState
  → lc_graph generate_node: build_chain(selected_model)
```

**Chain cache**: `_chain_cache: dict[str, RunnableWithMessageHistory]` trong `lc_chain.py` — tránh tạo lại `ChatOllama` object mỗi request.

**Env vars mới**: `OLLAMA_LARGE_MODEL`, `OLLAMA_SMALL_MODEL`, `ROUTER_ENABLED`.

## 🔄 Kiến trúc LangGraph (New Insights)

Backend pipeline hiện tại đã chuyển sang mô hình Node-based của LangGraph. Cụ thể luồng xử lý `ChatState`:
1. **Node `retrieve_memories`**: `hybrid_retrieve()` — BM25 + ChromaDB + RRF (Upgrade 1).
2. **Node `build_prompt`**: Render `ChatPromptTemplate` kết hợp persona, memory_context và user message.
3. **Node `generate`**: `build_chain(selected_model)` — dynamic model từ HeuristicRouter, stream token vào queue, bắt emotion tag.
4. **Node `store_memories`**: Ghi thông tin lượt thoại vào ChromaDB ngầm (background task).

> Nhờ tách bạch rõ từng node, logic RAG và LLM generation được phân giải độc lập, dễ dàng thay thế, debug qua LangSmith, đồng thời giữ latency thấp nhờ streaming realtime.

### 🧠 Fact Extraction Memory (Stage 5 — 2026-05-12)

Vấn đề: semantic search không recall được tên user vì query `"do you know my name"` có khoảng cách embedding xa so với `"user: my name is Truong"`.

Giải pháp:
- **`memory_middleware.py`**: Regex extraction — phát hiện `name`, `job`, `interest`, `location` từ user message ngay sau khi nhận.
- **`memory_store.py`**: `store_fact()` lưu documents `[FACT] name: Truong` với `doc_type="fact"`. `retrieve_facts()` always fetch tất cả facts của user. `retrieve_memories()` prepend facts trước semantic turn retrieval.

Context inject vào LLM:
```
Known facts about the user:
- [FACT] name: Truong

Relevant past conversation:
- ...
```

> **Stage 4 — DONE (2026-05-12):**
> - `fashion_girl_asian_girl.glb` đã được Blender 5.1 thêm 12 ARKit shape keys (jawOpen, mouthSmile_L/R, ...) qua script `add_shape_keys.py`.
> - Frontend: amplitude-based lip-sync fallback khi `RHUBARB_PATH` chưa set → `jawOpen` drive bằng audio RMS.
> - Để lip-sync phoneme-accurate: download Rhubarb binary → set `RHUBARB_PATH=./rhubarb/rhubarb.exe` trong `.env`.

## 🖥️ Kiến trúc UI (Claude Code Style)

Layout hiện tại dùng **flex row** 3 cột:
```
App.tsx
 └── flex-row wrapper (width/height 100%)
      ├── <Sidebar />       (240px fixed, z-index: 10)
      │    ├── Header: ◈ AI Chatbot
      │    ├── [+ New Chat] button
      │    ├── Recent sessions list (persist localStorage, max 20)
      │    └── Footer: TTS toggle | LLM select | status dot
      ├── <ChatInterface /> (flex:1, position: relative)
      │    ├── Empty state (khi messages=[])
      │    ├── Message list (user right / assistant left)
      │    └── Input bar (textarea + Send ▶ + Stop ◼)
      └── <RightSidebar />  (320px fixed, z-index: 10)
           ├── Settings Panel: 2 Dropdown (Model, Voice) gọi từ /api/
           └── <Scene /> container (Hiển thị Avatar 3D)
```

**Dynamic asset discovery:** Backend endpoints resolve asset folders from code location, not current working directory:
- `/api/models` → `frontend/public/models`
- `/api/voices` → `backend/voices`

RightSidebar uses custom React listbox dropdowns for Model/Voice instead of native `<select>` to avoid browser-native popup rendering only one visible row in the current Windows/Chromium runtime.

**Session & Project state** (Zustand + localStorage `chatbot_sessions`, `chatbot_projects`):
- `sessions: Session[]` — max 100, sort by `createdAt` desc
- `projects: Project[]` — list of folders
- `activeSessionId` — UUID của session đang xem
- `ttsEnabled: boolean` — persist `chatbot_tts_enabled`
- `createNewSession()` → UUID mới, reset messages
- `switchSession(id)` → save current, load target messages
- `renameSession(id, title)` / `renameProject(id, name)` — inline editing
- `moveSessionToProject(sid, pid)` — DND logic handler
- `saveCurrentSession()` — auto-gọi trong `addMessage()`

**TTS Toggle flow** (khi tắt):
```
Frontend gửi {tts_enabled: false}
  → Backend: _empty_audio() thay vì ElevenLabs → AudioChunkPayload {audio_base64: ""}
  → Frontend: skip decode/play, chỉ hiển thị text
  → Latency giảm đáng kể (không chờ TTS API)
```

## 🧠 Kiến trúc Hook quan trọng (App.tsx)

`App.tsx` là root duy nhất khởi tạo tất cả hooks — **tránh duplicate WebSocket/AudioContext**:
```
App.tsx
 ├── useWebSocket()  → { sendMessage, sendInterrupt }
 ├── useAudioQueue() → { stopPlayback }
 └── useVAD()        → onVoiceDetected: stopPlayback() + sendInterrupt()
      └── <ChatInterface sendMessage={} sendInterrupt={} />
```
**Quy tắc:** ChatInterface và các component con KHÔNG được tự gọi `useWebSocket()` hay `useAudioQueue()`.

## 🎭 Avatar — API cho Stage 4

File: `frontend/src/components/Avatar.tsx`
```ts
// Module-level ref — Stage 4 import trực tiếp
export const avatarMorphRef: {
  mesh: THREE.SkinnedMesh | null
  dict: Record<string, number>   // morphTargetDictionary
  influences: number[]           // live reference
}
export function setMorph(name: string, value: number): void
export function resetMorphs(names: string[]): void
```

File: `frontend/src/types/visemeMapping.ts`
```ts
export type RhubarbPhoneme = 'A'|'B'|'C'|'D'|'E'|'F'|'G'|'H'|'X'
export const VISEME_MAP: Record<RhubarbPhoneme, ARKitWeights>
export const ALL_VISEME_KEYS: string[]
```


## ⚠️ XTTS-v2 — Known Issues & Fixes (Python 3.12)

| Vấn đề | Fix |
|--------|-----|
| isin_mps_friendly ImportError (transformers>=4.47) | Patch env/.../tortoise/autoregressive.py: wrap import trong try/except, fallback 	orch.isin |
| is_torch_greater_or_equal ImportError (transformers<4.48) | Dùng 	ransformers>=4.48 |
| License prompt block server | os.environ["COQUI_TOS_AGREED"] = "1" trong _load_xtts_model() |
| pydantic ValidationError khi có env var lạ | xtra="ignore" trong Settings.model_config |
| Language vi is not supported | XTTS-v2 không hỗ trợ tiếng Việt — dùng XTTS_LANGUAGE=en |

**Ngôn ngữ XTTS-v2 hỗ trợ:** n, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, hu, ko, ja, hi
> Không có i — nếu cần tiếng Việt phải dùng ElevenLabs hoặc Edge-TTS.

**Patch file (phải làm lại nếu reinstall coqui-tts):**
`
File: venv/Lib/site-packages/TTS/tts/layers/tortoise/autoregressive.py
Dòng 11-12: thay thành:
try:
    from transformers.pytorch_utils import isin_mps_friendly as isin
except ImportError:
    isin = torch.isin
`

**Môi trường đã xác nhận:** Python 3.12.7 | torch 2.5.1+cu121 | RTX 3050 | coqui-tts 0.27.5 | transformers 4.48.x
## 🐳 Khởi chạy với Docker

```bash
cp backend/.env.example backend/.env
# Điền ELEVENLABS_API_KEY vào backend/.env
docker compose up --build
docker compose exec ollama ollama pull llama3:8b
# Truy cập http://localhost
```

## 🖥️ Khởi chạy Local Dev

```bash
# Backend
cd backend
venv/Scripts/activate       # Windows
venv/Scripts/python run.py  # → http://localhost:8000

# Frontend (terminal riêng)
cd frontend
npm run dev                 # → http://localhost:5173
```

## 🧠 Quy tắc cập nhật Brain
1. Mỗi khi hoàn thành một **feature mới** hoặc thay đổi **cấu trúc dự án**, bạn **BẮT BUỘC** phải cập nhật file `BRAIN.md` này.
2. Luôn giữ sơ đồ thư mục và bảng trạng thái Stage ở trạng thái cập nhật.

---
*Cập nhật lần cuối: 2026-05-13 (Dropdown asset discovery path fix)*
