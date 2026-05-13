# Plan: Claude Code–Style UI Simulator

## Context

Chatbot hiện tại có UI đơn giản — status bar + message list + input field overlay lên 3D scene. Mục tiêu là redesign UI theo style **Claude Code** (dark sidebar + main chat area), bổ sung:
- **Session management**: New Session button, Recent Sessions trong sidebar
- **TTS toggle**: User tắt/bật Text-to-Speech để phản hồi nhanh hơn (text-only mode)
- Giữ nguyên 3D avatar và toàn bộ backend pipeline

---

## Files cần sửa / tạo mới

| File | Action |
|------|--------|
| `frontend/src/store/chatStore.ts` | Thêm session state, ttsEnabled flag |
| `frontend/src/types/index.ts` | Thêm `Session` type, `tts_enabled` vào payload |
| `frontend/src/components/Sidebar.tsx` | **Tạo mới** — sidebar Claude Code style |
| `frontend/src/components/ChatInterface.tsx` | Refactor layout, bỏ status bar |
| `frontend/src/hooks/useWebSocket.ts` | Gửi `tts_enabled` + dùng `activeSessionId` |
| `frontend/src/hooks/useAudioQueue.ts` | Xử lý text-only chunk (không có audio_base64) |
| `frontend/src/App.tsx` | Render Sidebar cạnh ChatInterface |
| `backend/app/models.py` | Thêm `tts_enabled` field vào `UserMessagePayload` |
| `backend/app/main.py` | Parse `tts_enabled`, truyền vào pipeline |
| `backend/app/orchestrator.py` | Skip TTS khi `tts_enabled=False` |
| `BRAIN.md` | Cập nhật cấu trúc + stage status |
| `developer_log.md` | Ghi log task mới |

---

## Stage 1 — Session Management (Frontend Store + Types)

**Mục tiêu:** Lưu nhiều session trong Zustand + localStorage, mỗi session có messages riêng

### Tasks:
- [x] **1.1** Thêm `Session` type vào `frontend/src/types/index.ts`:
  ```ts
  export interface Session {
    id: string           // UUID
    title: string        // ~8 từ đầu của user message đầu tiên
    createdAt: number    // Date.now() timestamp
    messages: ChatMessage[]
  }
  ```
  Thêm `tts_enabled?: boolean` vào `UserMessagePayload`.

- [x] **1.2** Cập nhật `chatStore.ts` — thêm state và actions:
  ```ts
  // State mới
  sessions: Session[]         // tối đa 20, persist localStorage
  activeSessionId: string     // session đang hiển thị
  ttsEnabled: boolean         // persist localStorage, default true
  
  // Actions mới
  createNewSession()          // tạo UUID mới, reset messages, cập nhật activeSessionId
  switchSession(id)           // load messages từ session đó vào messages[]
  saveCurrentSession()        // upsert session hiện tại (gọi tự động trong addMessage)
  deleteSession(id)           // xóa session, nếu active → switch sang session mới nhất
  setTtsEnabled(val)          // toggle TTS
  ```
  - `sessionId` field đổi thành đọc từ `activeSessionId`
  - Auto-save: `addMessage()` gọi `saveCurrentSession()` sau mỗi tin
  - Max 20 sessions: xóa session cũ nhất nếu vượt

- [x] **1.3** `useWebSocket.ts` đọc `activeSessionId` thay vì `sessionId` cố định khi gửi `user_message`

---

## Stage 2 — Sidebar Component (Claude Code Style)

**Mục tiêu:** Sidebar 240px bên trái, dark navy, giống Claude Code

### Layout:
```
┌──────────────────────────────────────────────────────┐
│ [Sidebar 240px]      │  [Main Chat Area — flex:1]    │
│                      │  [3D Avatar Scene — bg layer] │
│  ◈ AI Chatbot        │                               │
│  ────────────────    │                               │
│  [+ New Chat]        │   message list                │
│                      │                               │
│  Recent              │   ...                         │
│  ● Hôm nay...        │                               │
│  • Xin chào AI...    │  ┌─────────────────────────┐  │
│  • What is LLM?...   │  │  Message AI...   [Send] │  │
│                      │  └─────────────────────────┘  │
│  ────────────────    │                               │
│  🔊 Voice  [toggle]  │                               │
│  Model: [dropdown]   │                               │
│  ● Connected         │                               │
└──────────────────────────────────────────────────────┘
```

### Tasks:
- [x] **2.1** Tạo `frontend/src/components/Sidebar.tsx`:

  **Header:**
  - Icon bot + chữ "AI Chatbot" (font monospace, màu `#e2e8f0`)

  **New Chat button:**
  - `+ New Chat` — full width, click → `createNewSession()` + WebSocket reconnect với sessionId mới
  - Style: border `rgba(255,255,255,0.1)`, hover indigo tint

  **Recent Sessions list:**
  - Map `sessions[]` theo `createdAt` giảm dần (mới nhất trên cùng)
  - Mỗi item: icon + title (truncate 28 chars) + timestamp relative
  - Click item → `switchSession(id)`
  - Active: `rgba(99,102,241,0.15)` bg + `2px solid #6366f1` border-left
  - Hover: hiện nút `×` xóa → kích hoạt inline confirm (xem Stage 5.4)

  **Footer:**
  - TTS Toggle: row "🔊 Voice" + switch on/off (`ttsEnabled` từ store)
  - LLM Provider select (di chuyển từ ChatInterface)
  - Connection status dot + text

- [x] **2.2** Styling (inline styles, không cần Tailwind):
  ```
  background: #151521
  border-right: 1px solid rgba(255,255,255,0.07)
  width: 240px
  font-family: 'JetBrains Mono', 'Fira Code', monospace
  ```

---

## Stage 3 — TTS Toggle (Backend + Frontend)

**Mục tiêu:** Khi TTS tắt, backend bỏ qua ElevenLabs/XTTS → phản hồi text ngay lập tức

### Backend:
- [x] **3.1** `backend/app/models.py`: thêm `tts_enabled: bool = True` vào `UserMessagePayload`

- [x] **3.2** `backend/app/main.py`: parse `tts_enabled` từ `data` dict trong `user_message` handler, truyền vào `_run_pipeline()`

- [x] **3.3** `backend/app/orchestrator.py` (hoặc `main.py` `_run_pipeline`):
  - Nhận tham số `tts_enabled: bool`
  - Nếu `tts_enabled=False`:
    - **Bỏ qua** `tts.synthesize()` và `get_visemes()`
    - Gửi `AudioChunkPayload` với `audio_base64=""`, `duration_ms=0`, `visemes=[]`
  - Nếu `tts_enabled=True`: pipeline hiện tại giữ nguyên

### Frontend:
- [x] **3.4** `chatStore.ts`: `ttsEnabled: boolean`, default `true`, persist `localStorage('chatbot_tts_enabled')`

- [x] **3.5** `useWebSocket.ts` → `sendMessage()` thêm `tts_enabled: useChatStore.getState().ttsEnabled` vào payload

- [x] **3.6** `useAudioQueue.ts`: khi `audio_base64` là chuỗi rỗng, skip decode/play (chỉ hiển thị text qua `addMessage` đã có sẵn)

---

## Stage 4 — Layout Refactor (App.tsx + ChatInterface.tsx)

**Mục tiêu:** Ghép Sidebar + ChatInterface thành layout ngang, Scene vẫn là background tuyệt đối

### Tasks:
- [x] **4.1** Cập nhật `App.tsx`:
  ```tsx
  <div style={{ position: 'relative', width: '100%', height: '100%' }}>
    {/* background 3D layer */}
    <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
      <Scene />
    </div>
    {/* UI layer */}
    <div style={{ position: 'absolute', inset: 0, zIndex: 10, display: 'flex' }}>
      <Sidebar sendSetModel={sendSetModel} />
      <ChatInterface sendMessage={sendMessage} sendInterrupt={handleInterrupt} />
    </div>
  </div>
  ```

- [x] **4.2** Cập nhật `ChatInterface.tsx`:
  - **Xóa** status bar (đã move sang Sidebar)
  - **Xóa** `sendSetModel` prop và LLM dropdown
  - Chiếm `flex: 1`, height `100%`, `display: flex`, `flexDirection: column`
  - Background: `rgba(0,0,0,0.45)` + `backdropFilter: blur(6px)` (nhìn xuyên thấy avatar)
  - Message list: `flex: 1`, `overflowY: auto`, padding `16px 20px`
  - Empty state: nếu `messages.length === 0` hiện welcome screen (xem Stage 5.2)

- [x] **4.3** Input area (Claude Code style):
  ```
  Container: border-radius 14px, border rgba(255,255,255,0.1), margin 0 16px 16px
  Textarea: không có border riêng, transparent bg, resize none
  Buttons bên phải: Send icon + Stop icon (khi isAISpeaking)
  ```

---

## Stage 5 — Polish & UX Details

- [x] **5.1** **Session title auto-generate**: lấy tối đa 8 từ đầu của user message đầu tiên trong session làm title. Nếu chưa có message → "New Chat"

- [x] **5.2** **Empty state / Welcome screen**: khi `messages = []`, hiển thị:
  ```
  ◈  AI Chatbot
  Xin chào! Tôi có thể giúp gì cho bạn hôm nay?
  [+ New Chat]  (shortcut hint)
  ```
  Center trong chat area, mờ nhẹ, biến mất khi có message đầu tiên

- [x] **5.3** **TTS-off badge**: khi `ttsEnabled = false`, hiện badge nhỏ "Text only ⚡" ngay trên input bar (màu amber)

- [x] **5.4** **Session delete inline confirm**: hover session item → nút `×` → click → item chuyển thành row "Xóa?" với nút Yes/No nhỏ, không dùng `window.confirm`

- [x] **5.5** **Timestamp relative**: helper `formatRelative(ts: number): string` trả về "Vừa xong", "5 phút trước", "Hôm qua", v.v.

- [x] **5.6** Cập nhật `BRAIN.md`: cập nhật file tree, stage table, architecture notes

- [x] **5.7** Cập nhật `developer_log.md`: xóa log cũ, ghi log task này

---

## Thứ tự implement

```
Stage 1 (types + store)
  → Stage 3 Backend (tts_enabled server-side)
  → Stage 2 (Sidebar component)
  → Stage 4 (App + ChatInterface layout)
  → Stage 3 Frontend (send flag + skip audio)
  → Stage 5 (polish)
```

> Backend TTS toggle làm trước Stage 2 để có thể test ngay khi toggle hoạt động.

---

## Verification Checklist

- [ ] **Session flow**: Tạo session → chat → tạo session mới → quay lại session cũ → messages còn nguyên
- [ ] **TTS off**: Gửi message khi TTS tắt → backend không gọi ElevenLabs → text hiện ngay, không có audio
- [ ] **TTS on**: Bật lại TTS → audio hoạt động bình thường như trước
- [ ] **Layout**: Sidebar 240px cố định + chat area đầy đủ, avatar nhìn xuyên qua glassmorphism
- [ ] **Delete session**: Hover → `×` → confirm inline → session bị xóa → active session chuyển đúng
- [ ] **Reconnect**: New Chat → WebSocket gửi `session_id` mới → backend nhận đúng
- [ ] **Backend health**: `GET /health` trả 200, WebSocket connect thành công

---

*Tạo: 2026-05-12 | Agent: Claude Sonnet 4.6*
