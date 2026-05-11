# Project Brain - Interactive 3D Chatbot

Chào Agent, đây là "bộ não" của dự án. File này chứa đựng cấu trúc tổng thể, trạng thái hiện tại và các kiến thức quan trọng để bạn nắm bắt dự án nhanh nhất.

## 🔗 Liên kết nhanh (Agent Guidelines)
- [Gemini Guidelines](gemini.md) - Hướng dẫn cho Gemini Agent.
- [Claude Guidelines](claude.md) - Hướng dẫn cho Claude Agent.
- [Developer Log](developer_log.md) - Nhật ký thay đổi và task hiện tại.

## 🏗️ Cấu trúc dự án (Current Architecture)

### 1. Backend (FastAPI)
- **Công nghệ:** Python, FastAPI, Ollama, ElevenLabs/Coqui API.
- **Nhiệm vụ:** Xử lý logic LLM (Llama 3), chuyển đổi văn bản sang âm thanh (TTS), và quản lý luồng dữ liệu qua WebSockets.

### 2. Frontend (React + Three Fiber)
- **Công nghệ:** React, Three.js, React Three Fiber (R3F), Zustand, TailwindCSS.
- **Nhiệm vụ:** Hiển thị model 3D (Ready Player Me), xử lý Lip-sync, và giao diện chat người dùng.

### 📁 Sơ đồ thư mục (File Tree)
```
interactive-chatbot/
├── backend/
│   └── app/
│       ├── config.py           # Settings (rhubarb_path mới từ Stage 4)
│       ├── models.py           # Pydantic models (VisemeEntry từ Stage 4)
│       ├── orchestrator.py     # LLM stream → sentence buffering
│       ├── tts_handler.py      # ElevenLabs TTS
│       ├── rhubarb_handler.py  # [Stage 4] Rhubarb lip-sync wrapper
│       └── main.py             # FastAPI WebSocket pipeline
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Avatar.tsx      # 3D avatar + emotion + lip-sync (useFrame)
│       │   ├── Scene.tsx       # R3F Canvas setup
│       │   └── ChatInterface.tsx
│       ├── hooks/
│       │   ├── useWebSocket.ts
│       │   ├── useAudioQueue.ts  # Audio playback + startLipSync/stopLipSync
│       │   └── useLipSync.ts     # [Stage 4] lipSyncState, tickLipSync
│       ├── store/chatStore.ts
│       └── types/
│           ├── index.ts          # VisemeKeyframe {start, end, value}
│           └── visemeMapping.ts  # VISEME_MAP (Rhubarb → ARKit weights)
│   └── public/models/avatar.glb  # Three.js facecap (52 ARKit blendshapes)
├── gemini.md
├── claude.md
├── BRAIN.md
├── developer_log.md
├── docker-compose.yml          # [Stage 5] ollama + backend + frontend
├── backend/
│   ├── Dockerfile              # [Stage 5] python:3.12-slim
│   └── .dockerignore
└── frontend/
    ├── Dockerfile              # [Stage 5] multi-stage: node build → nginx
    └── nginx.conf              # [Stage 5] SPA + /ws WebSocket proxy → backend:8000
```

## 🧠 Quy tắc cập nhật Brain
1. Mỗi khi hoàn thành một **feature mới** hoặc thay đổi **cấu trúc dự án**, bạn **BẮT BUỘC** phải cập nhật file `BRAIN.md` này để Agent tiếp theo có thông tin mới nhất.
2. Luôn giữ sơ đồ thư mục và danh sách công nghệ ở trạng thái cập nhật.

---
*Cập nhật lần cuối: 2026-05-10 (Stage 5 — Docker Compose Orchestration hoàn thành)*
