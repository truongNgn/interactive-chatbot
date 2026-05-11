# Hướng dẫn sử dụng — Interactive 3D Chatbot

> Tài liệu này dành cho người dùng cuối và developer muốn chạy hoặc tùy chỉnh dự án.
> Xem thêm: [BRAIN.md](BRAIN.md) · [WORKFLOW.md](WORKFLOW.md) · [Developer Log](developer_log.md)

---

## Yêu cầu hệ thống

| Thành phần | Tối thiểu | Ghi chú |
|-----------|-----------|---------|
| Python | 3.10+ | Backend |
| Node.js | 18+ | Frontend |
| Ollama | latest | Chạy LLM local |
| RAM | 8GB | 16GB nếu dùng XTTS-v2 |
| GPU (optional) | CUDA / MPS | Tăng tốc XTTS-v2 (~10x) |

---

## Cài đặt

### 1. Clone & chuẩn bị

```bash
git clone https://github.com/truongNgn/interactive-chatbot.git
cd interactive-chatbot
```

### 2. Cài Ollama và pull model

```bash
# Tải Ollama tại: https://ollama.com
ollama pull llama3:8b
```

### 3. Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Frontend

```bash
cd frontend
npm install
```

### 5. Avatar model

Tải file `facecap.glb` từ Three.js examples và đặt vào:
```
frontend/public/models/avatar.glb
```

> Download: [github.com/mrdoob/three.js — facecap.glb](https://github.com/mrdoob/three.js/blob/dev/examples/models/gltf/facecap.glb)

---

## Cấu hình TTS (chọn 1 trong 3)

Tạo file `backend/.env` từ template:

```bash
cp backend/.env.example backend/.env
```

### Lựa chọn A — ElevenLabs (cloud, có emotion control)

```env
ELEVENLABS_API_KEY=sk_xxxxxxxxxxxxxxxx
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
```

Đăng ký tại [elevenlabs.io](https://elevenlabs.io) để lấy API key.

---

### Lựa chọn B — Coqui XTTS-v2 (local, voice cloning miễn phí) ⭐

Dùng giọng nói của chính bạn hoặc bất kỳ giọng nào — chỉ cần 6-30 giây audio mẫu.

#### Bước 1: Cài thêm dependencies

```bash
cd backend
pip install TTS>=0.22.0 soundfile>=0.12.1
```

> Lần đầu chạy, XTTS-v2 sẽ tự tải model về (~2GB). Cần internet.

#### Bước 2: Chuẩn bị file giọng mẫu

Yêu cầu file WAV:
- **Thời lượng:** 6-30 giây (10 giây là tối ưu)
- **Chất lượng:** Không có tiếng ồn nền, giọng rõ ràng
- **Format:** WAV, sample rate 22050Hz trở lên
- **Nội dung:** Đọc bất kỳ đoạn văn nào rõ ràng, tự nhiên

```
backend/
└── voices/
    └── my_voice.wav    ← đặt file vào đây
```

#### Bước 3: Cấu hình `.env`

```env
# Để trống ElevenLabs → tự động dùng XTTS
ELEVENLABS_API_KEY=

# XTTS config
XTTS_SPEAKER_WAV=./voices/my_voice.wav
XTTS_LANGUAGE=vi
# XTTS_LANGUAGE=en    # nếu muốn tiếng Anh
```

**Ngôn ngữ hỗ trợ:** `en`, `vi`, `fr`, `de`, `es`, `it`, `pt`, `pl`, `tr`, `ru`, `nl`, `cs`, `ar`, `zh-cn`, `ja`, `ko`, `hu`

---

### Lựa chọn C — Text-only (không cần TTS)

```env
ELEVENLABS_API_KEY=
XTTS_SPEAKER_WAV=
```

Avatar vẫn hiển thị và phản ứng cảm xúc, nhưng không có giọng nói.

---

## Chạy dự án

### Local Development

```bash
# Terminal 1 — Backend
cd backend
venv\Scripts\activate        # Windows
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Truy cập: **http://localhost:5173**

### Kiểm tra backend

```bash
curl http://localhost:8000/health
```

Response mẫu khi dùng XTTS:
```json
{
  "status": "ok",
  "llm": { "model": "llama3:8b", "ready": true },
  "tts": { "provider": "xtts", "ready": true }
}
```

---

## Chạy với Docker

```bash
cp backend/.env.example backend/.env
# Điền config TTS vào backend/.env

docker compose up --build

# Pull Ollama model (lần đầu)
docker compose exec ollama ollama pull llama3:8b
```

Truy cập: **http://localhost**

> **Lưu ý khi dùng XTTS trong Docker:** Mount thư mục voices vào container. Thêm vào `docker-compose.yml`:
> ```yaml
> backend:
>   volumes:
>     - ./backend/voices:/app/voices
> ```

---

## Sử dụng

### Giao tiếp bằng text
Nhập tin nhắn vào ô chat và nhấn **Enter** hoặc nút gửi.

### Giao tiếp bằng giọng nói
Ứng dụng tự động lắng nghe microphone. Khi bạn nói trong lúc AI đang trả lời, AI sẽ **tự động dừng** và lắng nghe bạn (VAD interrupt).

> Lần đầu truy cập, trình duyệt sẽ hỏi quyền microphone — chọn **Allow**.

### Cảm xúc Avatar
Avatar tự động thể hiện cảm xúc theo nội dung câu trả lời:

| Cảm xúc | Biểu hiện |
|---------|-----------|
| Joy | Cười, gò má nâng |
| Sad | Miệng cong xuống, lông mày nhíu |
| Surprise | Mắt mở to, miệng hé |
| Anger | Lông mày cau, mũi nhăn |
| Thinking | Lông mày hơi nhướng |
| Neutral | Biểu cảm bình thường |

---

## Biến môi trường đầy đủ

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `OLLAMA_HOST` | `http://localhost:11434` | Địa chỉ Ollama server |
| `OLLAMA_MODEL` | `llama3:8b` | Model LLM |
| `ELEVENLABS_API_KEY` | _(trống)_ | API key ElevenLabs |
| `ELEVENLABS_VOICE_ID` | `21m00Tcm4TlvDq8ikWAM` | ID giọng ElevenLabs |
| `ELEVENLABS_MODEL_ID` | `eleven_turbo_v2_5` | Model TTS ElevenLabs |
| `XTTS_SPEAKER_WAV` | _(trống)_ | Path file WAV giọng mẫu |
| `XTTS_LANGUAGE` | `vi` | Ngôn ngữ XTTS |
| `XTTS_MODEL_NAME` | `tts_models/multilingual/multi-dataset/xtts_v2` | Model XTTS |
| `HOST` | `0.0.0.0` | Host backend |
| `PORT` | `8000` | Port backend |
| `LOG_LEVEL` | `INFO` | Level log (DEBUG/INFO/WARNING) |

---

## Xử lý sự cố thường gặp

**Lỗi: `Could not load avatar.glb: setKTX2Loader must be called`**
→ Đảm bảo đã đặt đúng file `avatar.glb` vào `frontend/public/models/`. File phải là Three.js facecap GLB.

**Lỗi: `WebSocket connection failed`**
→ Backend chưa chạy. Kiểm tra `uvicorn` đang lắng nghe trên port 8000.

**XTTS chạy rất chậm**
→ Không có GPU. Cân nhắc dùng ElevenLabs hoặc chấp nhận latency 2-4s/câu trên CPU.

**XTTS: `XTTS_SPEAKER_WAV không tồn tại`**
→ Kiểm tra đường dẫn trong `.env`. Path tương đối tính từ thư mục `backend/`.

**Ollama model not found**
→ Chạy `ollama pull llama3:8b` để tải model về trước.

---

*Cập nhật lần cuối: 2026-05-06*
