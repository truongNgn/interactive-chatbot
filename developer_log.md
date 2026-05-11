# Developer Log - Interactive 3D Chatbot

> **Quy tắc:** Xóa log task cũ khi bắt đầu task mới. Luôn link đến [BRAIN.md](BRAIN.md).

---

## Task: XTTS-v2 Setup hoàn chỉnh + Custom Avatar + Bug Fixes
**Agent:** Claude (Senior AI Engineer)
**Status:** ✅ Completed
**Date:** 2026-05-07

### Nội dung thực hiện

#### 1. Bug Fixes (Frontend)

**`frontend/src/components/Avatar.tsx`**
- Fix `THREE.GLTFLoader: setKTX2Loader must be called` — thêm `KTX2Loader` qua `useGLTF extendLoader` + `useThree`
- Xóa `useGLTF.preload(AVATAR_PATH)` — nguyên nhân gốc gây cache lỗi trước khi KTX2Loader ready
- Fix TypeScript: cast `ktx2 as any` để tránh type conflict giữa `three` và `three-stdlib`

**`frontend/src/hooks/useWebSocket.ts`**
- Fix "WebSocket closed before connection established": guard `readyState !== WebSocket.CLOSED`

**`frontend/src/hooks/useVAD.ts`**
- Fix TypeScript: cast `Float32Array<ArrayBuffer>` cho `getFloatTimeDomainData()`

#### 2. Custom Avatar — `fashion_girl_asian_girl.glb`

**`frontend/src/components/Avatar.tsx`** [REWRITTEN]
- Đổi `AVATAR_PATH` → `/models/fashion_girl_asian_girl.glb`
- Hướng A (static display): model không có ARKit blendshapes, hiển thị tĩnh
- Điều kiện tìm morph mesh nới lỏng: `> 0` thay vì `> 10`
- Idle animation: body sway (`rotation.y` + `position.y` sin wave) thay vì head bob
- Fallback shape: `capsuleGeometry` thay vì sphere
- morph/emotion logic vẫn giữ — no-op nếu model không có blendshapes

**`frontend/src/components/Scene.tsx`** [UPDATED]
- Camera: `position=[0,1,3.5]`, `fov=50`, `far=50` — full-body view
- `OrbitControls target=[0,1,0]` — nhìn ngang hông nhân vật
- `ContactShadows position=[0,-0.01,0]` — đổ bóng xuống sàn
- minDistance=1.5, maxDistance=6

#### 3. XTTS-v2 Voice Cloning — Setup hoàn chỉnh

**Quá trình setup (ghi lại để Agent sau tránh lặp lại):**

| Vấn đề | Nguyên nhân | Fix |
|--------|------------|-----|
| Server crash khi start | `CoquiXTTSHandler.__init__` load model ngay lúc startup | Chuyển sang lazy load trong `_get_tts()` |
| `ImportError: isin_mps_friendly` | `transformers>=4.47` xóa hàm này | Patch `venv/.../tortoise/autoregressive.py`: `try/except ImportError → torch.isin` |
| `ImportError: is_torch_greater_or_equal` | `transformers<4.48` chưa có hàm này | Nâng lên `transformers>=4.48` |
| License prompt block server | XTTS hỏi đồng ý CPML interactively | Set `os.environ["COQUI_TOS_AGREED"] = "1"` trong code |
| `ValidationError: extra inputs not permitted` | `COQUI_TOS_AGREED=1` trong `.env` bị pydantic-settings reject | Xóa khỏi `.env`, set trong code + thêm `extra="ignore"` vào Settings |
| `Language vi is not supported` | XTTS-v2 không hỗ trợ tiếng Việt | Đổi `XTTS_LANGUAGE=en` |

**Files đã thay đổi:**
- `backend/app/tts_handler.py` — lazy load, phân tách ImportError, auto-accept license, GPU detect
- `backend/app/config.py` — thêm `extra="ignore"`, xtts settings
- `backend/app/main.py` — startup log phân biệt provider
- `backend/requirements.txt` — thêm `coqui-tts`, `soundfile`
- `backend/.env` — `ELEVENLABS_API_KEY=` (trống), `XTTS_SPEAKER_WAV`, `XTTS_LANGUAGE=en`

**Patch thủ công trong venv (phải làm lại nếu reinstall coqui-tts):**
```
venv/Lib/site-packages/TTS/tts/layers/tortoise/autoregressive.py — line 11-12:
try:
    from transformers.pytorch_utils import isin_mps_friendly as isin
except ImportError:
    isin = torch.isin
```

**Môi trường đã xác nhận hoạt động:**
- Python 3.12.7
- torch 2.5.1+cu121 (NVIDIA RTX 3050 Laptop GPU)
- coqui-tts 0.27.5
- transformers 4.48.x
- soundfile 0.13.1
- XTTS model: `tts_models/multilingual/multi-dataset/xtts_v2` (~2GB, cache tại `C:\Users\...\AppData\Local\tts\`)
- Voice sample: `backend/voices/NT_Voice_full.wav`
- Language: `en` (XTTS-v2 không hỗ trợ `vi`)

#### 4. Tài liệu mới

- `WORKFLOW.md` [NEW] — data flow, interrupt flow, emotion system
- `GUIDE.md` [NEW] — hướng dẫn cài đặt đầy đủ

### Ghi chú cho Agent tiếp theo (Stage 4 — Lip-sync)
- Avatar hiện tại (`fashion_girl_asian_girl.glb`) **không có blendshapes** → Stage 4 lip-sync sẽ cần:
  - Thay model có ARKit blendshapes (Ready Player Me / facecap), HOẶC
  - Rig blendshapes vào model hiện tại qua Blender
- `avatarMorphRef`, `setMorph()`, `resetMorphs()` sẵn sàng trong `Avatar.tsx`
- `VISEME_MAP`, `ALL_VISEME_KEYS` trong `frontend/src/types/visemeMapping.ts`
- Backend cần Rhubarb binary để điền `AudioChunkPayload.visemes[]`
- **Xóa log này khi bắt đầu Stage 4**

---
