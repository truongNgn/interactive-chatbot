# Developer Log - Interactive 3D Chatbot

> [!IMPORTANT]
> **Quy tắc quản lý Log:**
> 1. Mỗi khi bắt đầu một task mới, Agent **phải xóa các log của task cũ** để tiết kiệm dung lượng và giữ file súc tích.
> 2. Luôn cập nhật trạng thái task hiện tại.
> 3. Liên kết đến [BRAIN.md](BRAIN.md), [Gemini.md](gemini.md), và [Claude.md](claude.md).

---

## Task: Stage 5 — Docker Compose Orchestration
**Agent:** Claude (Senior AI Engineer)
**Status:** Completed
**Date:** 2026-05-10

### Các file được tạo:

| File | Mô tả |
|---|---|
| `backend/Dockerfile` | Python 3.12-slim, cài requirements, expose 8000 |
| `backend/.dockerignore` | Exclude `__pycache__`, `.env`, venv |
| `frontend/Dockerfile` | Multi-stage: Node 20 build → Nginx 1.27 serve |
| `frontend/nginx.conf` | SPA fallback + `/ws` WebSocket proxy → backend:8000 |
| `frontend/.dockerignore` | Exclude `node_modules`, `dist` |
| `docker-compose.yml` | 3 services: ollama + backend + frontend |
| `backend/.env.example` | Cập nhật thêm `RHUBARB_PATH` |

### Cách chạy:

```bash
# 1. Tạo file .env từ example
cp backend/.env.example backend/.env
# Điền ELEVENLABS_API_KEY và các biến cần thiết

# 2. Build & start toàn bộ stack
docker compose up --build

# 3. Pull Ollama model lần đầu (chạy trong container đang chạy)
docker exec chatbot-ollama ollama pull llama3:8b

# 4. Truy cập
# Frontend: http://localhost
# Backend API: http://localhost:8000/health
```

### Kiến trúc mạng trong Docker:
- `frontend` (Nginx:80) → proxy `/ws` → `backend:8000`
- `backend` → `ollama:11434` (qua Docker internal network)
- Ollama model data được persist qua volume `ollama_data`

### Lip-sync trong Docker (optional):
```yaml
# Uncomment trong docker-compose.yml:
volumes:
  - /path/to/rhubarb:/usr/local/bin/rhubarb:ro
# Thêm vào backend/.env:
RHUBARB_PATH=/usr/local/bin/rhubarb
```

### GPU support (NVIDIA):
Uncomment phần `deploy.resources.reservations` trong service `ollama` của `docker-compose.yml`.

---
