# Project Workflow — Interactive 3D Chatbot

> Tài liệu này mô tả luồng dữ liệu, kiến trúc runtime và quy trình phát triển của dự án.
> Xem thêm: [BRAIN.md](BRAIN.md) · [CLAUDE.md](CLAUDE.md) · [Developer Log](developer_log.md)

---

## 1. Kiến trúc tổng quan

```
┌──────────────────────────────────────────────────────────────────┐
│                        BROWSER (Frontend)                        │
│                                                                  │
│  Microphone ──► useVAD ──► interrupt signal                      │
│                                                                  │
│  ChatInterface (text input)                                      │
│        │                                                         │
│        ▼                                                         │
│  useWebSocket ◄──────────────────────────────────────────────►  │
│        │               WebSocket ws://localhost:8000/ws/chat     │
│        ▼                                                         │
│  useAudioQueue ──► Web Audio API ──► Speaker                     │
│        │                                                         │
│        ▼                                                         │
│  chatStore (Zustand) ──► currentEmotion, isAISpeaking            │
│        │                                                         │
│        ▼                                                         │
│  Scene (R3F Canvas)                                              │
│    └── Avatar (GLBAvatar)                                        │
│          ├── useFrame: blink + emotion lerp + head bob           │
│          └── avatarMorphRef ◄── lip-sync (Stage 4)              │
└──────────────────────────────────────────────────────────────────┘
                              │  WebSocket
┌──────────────────────────────────────────────────────────────────┐
│                        SERVER (Backend)                          │
│                                                                  │
│  FastAPI /ws/chat                                                │
│        │                                                         │
│        ▼                                                         │
│  Orchestrator                                                    │
│    └── LLMHandler ──► Ollama (Llama 3) streaming tokens         │
│          │                                                       │
│          ▼ sentence-buffering (dấu câu / clause)                │
│    SentenceChunk { text, emotion }                               │
│          │                                                       │
│          ▼                                                       │
│  TTSHandler                                                      │
│    ├── ElevenLabsTTSHandler (có API key)                        │
│    └── NoOpTTSHandler      (fallback text-only)                 │
│          │                                                       │
│          ▼                                                       │
│  AudioChunkPayload { text, emotion, audio_base64 }              │
│          │──────────────────────────────► WebSocket send        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Luồng dữ liệu chi tiết (Data Flow)

### 2.1 User gửi tin nhắn

```
[User nhập text]
      │
      ▼
ChatInterface.tsx
      │  sendMessage(text)
      ▼
useWebSocket.ts
      │  ws.send({ type: "user_message", text })
      ▼
WebSocket → Backend /ws/chat
```

### 2.2 Backend xử lý (Pipeline)

```
Nhận { type: "user_message", text }
      │
      ▼
Orchestrator.run(user_text, sentence_queue)          [asyncio.Task]
      │
      ├── LLMHandler.stream_tokens(user_text)
      │         │  Ollama Llama 3 — streaming tokens
      │         ▼
      │   buffer += token
      │         │
      │         ├── _should_flush? (dấu .!? hoặc ,; nếu buffer ≥ 40 ký tự)
      │         │         ▼  YES
      │         │   _flush_buffer(buffer)
      │         │         │  _parse_emotion() → bóc [emotion_tag]
      │         │         ▼
      │         │   SentenceChunk { text, emotion } → sentence_queue
      │         │
      │         └── ... tiếp tục token tiếp theo
      │
      │   [Flush phần còn lại cuối stream]
      │         ▼
      │   sentinel None → sentence_queue
      │
      ▼
Consumer loop (main.py _run_pipeline):
      │
      ├── chunk = await sentence_queue.get()
      │         │
      │         ▼
      │   TTSHandler.synthesize(chunk)
      │         │  ElevenLabs: emotion → VoiceSettings → audio bytes
      │         │  NoOp: trả về b""
      │         ▼
      │   AudioChunkPayload {
      │     text, emotion, audio_base64
      │   }
      │         │
      │         ▼
      │   websocket.send_text(payload.json())
      │
      └── [chunk == None] → send DonePayload → kết thúc
```

### 2.3 Frontend nhận và phát

```
useWebSocket.ts onmessage
      │
      ├── type == "audio_chunk"
      │         ├── addMessage() → hiển thị text lên ChatInterface
      │         └── enqueueAudio(msg) → useAudioQueue
      │
      ├── type == "done"
      │         └── (audio queue tự drain)
      │
      ├── type == "clear_queue"
      │         └── clearQueue() → dừng audio ngay lập tức
      │
      └── type == "error"
                └── addMessage() với prefix ⚠

useAudioQueue.ts
      │  decode audio_base64 → ArrayBuffer
      │  AudioContext.decodeAudioData()
      │  Xếp hàng → phát tuần tự
      │  Cập nhật isAISpeaking, currentEmotion → chatStore
      ▼
Web Audio API → Speaker
```

### 2.4 Avatar phản ứng (3D)

```
chatStore.currentEmotion (thay đổi theo từng audio chunk)
      │
      ▼
Avatar.tsx — useFrame (60fps)
      ├── Blink: eyeBlink_L / eyeBlink_R (timer ngẫu nhiên 2-5s)
      ├── Emotion lerp: morph targets → EMOTION_MORPHS[currentEmotion]
      │     joy:      mouthSmile, cheekSquint
      │     sad:      mouthFrown, browInnerUp
      │     surprise: eyeWide, jawOpen, browOuterUp
      │     anger:    browDown, noseSneer
      │     thinking: browInnerUp, browDown_L
      └── Head bob: sin wave (rotation.z, rotation.x)
```

---

## 3. Interrupt Flow (User ngắt AI)

```
[User nói trong khi AI đang nói]
      │
      ▼
useVAD.ts — voice detected
      │
      ├── stopPlayback() → dừng Web Audio ngay
      └── sendInterrupt() → ws.send({ type: "interrupt" })
                                    │
                                    ▼
                        Backend: _cancel_current()
                              │  orchestrator.interrupt()
                              │  current_task.cancel()
                              ▼
                        ws.send({ type: "clear_queue" })
                              │
                              ▼
                        Frontend: clearQueue() → chatStore reset
```

---

## 4. Emotion System

LLM được hướng dẫn (system prompt) prepend emotion tag vào **mỗi câu**:

| Tag | Trigger | VoiceSettings (ElevenLabs) | Avatar morphs |
|-----|---------|---------------------------|---------------|
| `[joy]` | Vui, tích cực | stability=0.30, style=0.55 | mouthSmile, cheekSquint |
| `[sad]` | Buồn, cảm thông | stability=0.85, style=0.10 | mouthFrown, browInnerUp |
| `[neutral]` | Thông tin thông thường | stability=0.50, style=0.00 | (reset) |
| `[thinking]` | Suy nghĩ, tính toán | stability=0.70, style=0.10 | browInnerUp, browDown_L |
| `[surprise]` | Ngạc nhiên | stability=0.20, style=0.70 | eyeWide, jawOpen, browOuterUp |
| `[anger]` | Bực bội, phản đối | stability=0.30, style=0.80 | browDown, noseSneer |

Orchestrator bóc tag bằng regex `^\s*\[(joy|sad|...)\]\s*` trước khi đưa vào TTS.

---

## 5. Error Handling & Fallback

| Tình huống | Hành vi |
|-----------|---------|
| Ollama không chạy | `health_check()` warn lúc startup, LLM stream raise → WebSocket gửi `ErrorPayload` |
| ElevenLabs lỗi / không có API key | `NoOpTTSHandler` trả về `b""` → `audio_base64=""` → Frontend hiển thị text, không phát audio |
| TTS timeout trong pipeline | `audio_bytes = b""` (graceful fallback), pipeline tiếp tục câu kế |
| WebSocket disconnect | `_cancel_current()` → huỷ task, giải phóng resource |
| GLB load lỗi (KTX2 textures) | `KTX2Loader` được cấu hình trong `useGLTF extendLoader`, `<Suspense>` hiển thị sphere fallback trong khi load |

---

## 6. Khởi động dự án

### Backend
```bash
cd backend
python -m venv venv && source venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### Biến môi trường (backend)
```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3
ELEVENLABS_API_KEY=<optional>
ELEVENLABS_VOICE_ID=<optional>
```

---

## 7. Sơ đồ thư mục

```
interactive-chatbot/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI app, WebSocket /ws/chat, pipeline runner
│       ├── orchestrator.py  # LLM stream → sentence buffering → SentenceChunk queue
│       ├── llm_handler.py   # Ollama client, system prompt, stream_tokens()
│       ├── tts_handler.py   # ElevenLabs / NoOp TTS, emotion→VoiceSettings
│       ├── models.py        # Pydantic models (SentenceChunk, AudioChunkPayload…)
│       └── config.py        # Settings từ env vars
│
├── frontend/src/
│   ├── App.tsx              # Root: kết nối WS + VAD + layout
│   ├── components/
│   │   ├── Scene.tsx        # R3F Canvas, lighting, OrbitControls
│   │   ├── Avatar.tsx       # GLB load (KTX2), morph targets, blink, emotion lerp
│   │   └── ChatInterface.tsx# Chat UI overlay
│   ├── hooks/
│   │   ├── useWebSocket.ts  # WS connect/reconnect, message dispatch
│   │   ├── useAudioQueue.ts # Audio decode, sequential playback, isAISpeaking
│   │   └── useVAD.ts        # Voice Activity Detection → interrupt
│   ├── store/
│   │   └── chatStore.ts     # Zustand: messages, wsStatus, currentEmotion, isAISpeaking
│   └── types/
│       ├── index.ts         # Shared TypeScript types
│       └── visemeMapping.ts # ARKit viseme → morph name map (Stage 4)
│
├── BRAIN.md                 # Bộ não dự án — cấu trúc & trạng thái
├── WORKFLOW.md              # File này — luồng dữ liệu & kiến trúc runtime
├── CLAUDE.md                # Guidelines cho Claude Agent
└── developer_log.md         # Nhật ký công việc
```

---

*Cập nhật lần cuối: 2026-05-06*
