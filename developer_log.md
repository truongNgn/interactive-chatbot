# Developer Log - Interactive 3D Chatbot

## Task: Stage 3 — 3D Frontend (React + R3F)
**Agent:** Claude (Senior AI Engineer)
**Status:** Completed
**Date:** 2026-04-07

### Cấu trúc thư mục tạo ra:
```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx                       # Layout: Scene (3D) + ChatInterface overlay
│   ├── types/index.ts                # TypeScript types mirror backend models
│   ├── store/chatStore.ts            # Zustand: wsStatus, audioQueue, emotion, messages
│   ├── hooks/
│   │   ├── useWebSocket.ts           # WS connect + auto-reconnect + message routing
│   │   └── useAudioQueue.ts          # Web Audio API sequential playback
│   └── components/
│       ├── Avatar.tsx                # R3F GLB loader + placeholder geometry + idle anim
│       ├── Scene.tsx                 # Canvas + PBR lights + Environment + OrbitControls
│       └── ChatInterface.tsx         # Text input + message history + status bar + interrupt
├── public/models/                    # Đặt avatar.glb vào đây (Ready Player Me)
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### Quyết định kỹ thuật:

**1. Audio Queue (`useAudioQueue`):**
- Dùng Web Audio API (`AudioContext.decodeAudioData`) thay vì `<audio>` tag để kiểm soát chính xác timing cho lip-sync Stage 4
- `AudioBufferSourceNode.onended` → tự động pop chunk tiếp theo → zero-gap playback giữa các câu
- Text-only fallback: nếu `audio_base64 = ""` → cập nhật emotion, skip playback

**2. Avatar (`Avatar.tsx`):**
- `Suspense` + `useGLTF` load model từ `/models/avatar.glb`
- Fallback `AvatarPlaceholder` (geometric shape) khi chưa có GLB
- `morphTargetInfluences` đã sẵn sàng cho Stage 4 (Rhubarb visemes + emotion blendshapes)

**3. WebSocket (`useWebSocket`):**
- Auto-reconnect sau 3 giây khi disconnect
- Route: `audio_chunk` → store.enqueueAudio | `clear_queue` → store.clearQueue
- Interrupt: gửi `{"type":"interrupt"}` + local clearQueue để avatar dừng ngay

**4. Build:**
- `npm run build` → `✓ built in 6.28s` (TypeScript OK, no errors)
- Bundle lớn (~1.1MB) là bình thường với Three.js — sẽ code-split ở Stage 5

### Cách chạy:
```bash
cd frontend
npm run dev        # http://localhost:5173
```
Backend phải chạy trước tại `localhost:8000` (Vite proxy `/ws` → backend).

### Cần chuẩn bị trước Stage 4:
1. Xuất avatar `.glb` từ [Ready Player Me](https://readyplayer.me) với ARKit blendshapes
2. Đặt vào `frontend/public/models/avatar.glb`
3. Kiểm tra model có `morphTargetDictionary` với các key viseme: `viseme_AA`, `viseme_O`, `viseme_PP`, v.v.

---
*Stage 4 (Animation & Lip-sync) — Rhubarb trên backend + morphTargetInfluences trên frontend.*
