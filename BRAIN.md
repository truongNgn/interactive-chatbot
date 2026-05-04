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
├── backend/                  # Logic xử lý AI & TTS
├── frontend/                 # Giao diện React & 3D Scene
│   ├── src/
│   │   ├── components/       # Avatar, Scene, ChatInterface
│   │   ├── hooks/            # useWebSocket, useAudioQueue
│   │   ├── store/            # chatStore (Zustand)
│   │   └── types/            # TypeScript definitions
│   └── public/models/        # Chứa avatar.glb
├── gemini.md                 # Guideline cho Gemini
├── claude.md                 # Guideline cho Claude
├── BRAIN.md                  # Tài liệu cấu trúc & bộ não dự án
├── developer_log.md          # Nhật ký công việc (Auto-pruning)
└── docker-compose.yml        # Orchestration (Stage 5)
```

## 🧠 Quy tắc cập nhật Brain
1. Mỗi khi hoàn thành một **feature mới** hoặc thay đổi **cấu trúc dự án**, bạn **BẮT BUỘC** phải cập nhật file `BRAIN.md` này để Agent tiếp theo có thông tin mới nhất.
2. Luôn giữ sơ đồ thư mục và danh sách công nghệ ở trạng thái cập nhật.

---
*Cập nhật lần cuối: 2026-05-04*
