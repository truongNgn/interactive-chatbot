# Project Brain - Interactive 3D Chatbot

Chào Agent, đây là "bộ não" của dự án. File này chứa đựng cấu trúc tổng thể, trạng thái hiện tại và các kiến thức quan trọng để bạn nắm bắt dự án nhanh nhất.

## 🔗 Liên kết nhanh (Agent Guidelines)
- [Gemini Guidelines](gemini.md) - Hướng dẫn cho Gemini Agent.
- [Claude Guidelines](claude.md) - Hướng dẫn cho Claude Agent.
- [Developer Log](developer_log.md) - Nhật ký thay đổi và task hiện tại.

## 🏗️ Cấu trúc dự án (Current Architecture)

### 1. Backend (FastAPI)
- **Công nghệ:** Python 3.12, FastAPI, Ollama (Llama 3:8b), ElevenLabs SDK 1.50.3, Coqui TTS (XTTS-v2, optional).
- **Nhiệm vụ:** Xử lý logic LLM, sentence-buffering, TTS, stream qua WebSocket.
- **venv:** `backend/venv/` — activate bằng `venv/Scripts/activate` (Windows).

### 2. Frontend (React + Three Fiber)
- **Công nghệ:** React 18, Vite 5, TypeScript, R3F v8, Drei v9, Zustand v4.
- **Avatar:** `fashion_girl_asian_girl.glb` — full-body custom character, không có ARKit blendshapes (hướng A - static display). File `avatar.glb` (facecap) vẫn còn trong `/models/` để dùng Stage 4.
- **Nhiệm vụ:** Hiển thị 3D avatar, audio queue, lip-sync, VAD auto-interrupt.

### 3. Deployment (Docker)
- **docker-compose.yml** — 3 services: `frontend` (Nginx), `backend` (FastAPI), `ollama`
- Volume `ollama_data` giữ model qua các lần restart.

### 📁 Sơ đồ thư mục (File Tree)
```
interactive-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, WebSocket /ws/chat, /health
│   │   ├── orchestrator.py   # Token streaming + sentence-buffering (regex flush)
│   │   ├── llm_handler.py    # Ollama Llama 3 — async stream, system prompt emotion tags
│   │   ├── tts_handler.py    # ElevenLabs / Coqui XTTS-v2 / NoOp — factory pattern, BaseTTSHandler
│   │   ├── models.py         # Pydantic: Emotion, SentenceChunk, AudioChunkPayload, ...
│   │   └── config.py         # pydantic-settings (.env): ollama, elevenlabs, server
│   ├── venv/                 # Python virtual environment
│   ├── Dockerfile
│   ├── run.py                # Entry point: uvicorn --reload
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Avatar.tsx        # GLB loader, traverse morph mesh, avatarMorphRef, idle blink,
│   │   │   │                     # emotion blendshapes (lerp), setMorph()/resetMorphs() exports
│   │   │   ├── Scene.tsx         # R3F Canvas (fov:38, z:1.4 cho head model), PBR lighting
│   │   │   └── ChatInterface.tsx # Props: {sendMessage, sendInterrupt} — không self-hook
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts   # WS connect + auto-reconnect (3s) + message routing
│   │   │   ├── useAudioQueue.ts  # Web Audio API sequential playback, onended→next chunk
│   │   │   └── useVAD.ts         # Voice Activity Detection (RMS, AnalyserNode) → auto-interrupt
│   │   ├── store/
│   │   │   └── chatStore.ts      # Zustand: wsStatus, messages, audioQueue, isAISpeaking, currentEmotion
│   │   ├── types/
│   │   │   ├── index.ts          # WS payload types: AudioChunkPayload, VisemeKeyframe, ...
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
└── implementation_plan.md
```

## ✅ Trạng thái các Stage

| Stage | Tên | Trạng thái |
|-------|-----|-----------|
| 1 | AI Core & Token Streaming (FastAPI + Ollama + WebSocket) | ✅ Hoàn thành |
| 2 | TTS Integration (ElevenLabs + Coqui XTTS-v2 voice cloning + emotion mapping) | ✅ Hoàn thành |
| 3 | 3D Frontend (R3F + Avatar + AudioQueue) — **Tier 3 facecap** | ✅ Hoàn thành |
| 4 | Lip-sync & Emotion Blendshapes (Rhubarb → ARKit) | ⏳ Chưa thực hiện |
| 5 | Interruption (VAD) + Docker | ✅ Hoàn thành |

> **Lưu ý Stage 4:** Backend cần tích hợp Rhubarb Lip Sync binary để điền `visemes[]` vào `AudioChunkPayload`. Frontend đã có `VISEME_MAP` và `avatarMorphRef` sẵn sàng tiếp nhận.

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
*Cập nhật lần cuối: 2026-05-07 (XTTS-v2 working + custom avatar + bug fixes)*
