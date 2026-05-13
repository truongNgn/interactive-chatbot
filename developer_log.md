# Developer Log - Interactive 3D Chatbot

> **Quy tắc:** Xóa log task cũ khi bắt đầu task mới. Luôn link đến [BRAIN.md](BRAIN.md).

---

## Task: Fix Model/Voice Dropdown Asset Discovery
**Agent:** Codex (Senior AI Engineer)
**Status:** Done
**Date:** 2026-05-13

### Thay đổi

#### `backend/app/main.py`
- Sửa `/api/models` và `/api/voices` dùng absolute path dựa trên vị trí file backend thay vì current working directory.
- `/api/models` hiện đọc ổn định từ `frontend/public/models`.
- `/api/voices` hiện đọc ổn định từ `backend/voices`.
- Sort danh sách trả về và match extension không phân biệt hoa/thường.

#### `frontend/src/components/RightSidebar.tsx`
- Thay native `<select>` cho Model/Voice bằng custom listbox dropdown.
- Lý do: API live đã trả đủ data, DOM native `<select>` cũng có đủ option, nhưng popup native trên UI chỉ hiển thị một dòng trong runtime hiện tại.
- Custom dropdown render trực tiếp trong React nên hiển thị đủ mọi option và tránh phụ thuộc vào native select popup.

### Test kết quả
- `get_models()` trả về `avatar.glb`, `donghua_girl_1.glb`, `fashion_girl_asian_girl.glb`.
- `get_voices()` trả về `31_Future Samples_Anime Vocals_Vocal 27.wav`, `NT_Voice_full.wav`.
- Root cause: endpoint dùng relative path nên khi backend chạy từ working directory khác, API chỉ thấy thiếu hoặc sai folder asset.
- Browser DOM verify: Model dropdown có 3 `role="option"`, Voice dropdown có 2 `role="option"`.
- `npm run build` chưa pass vì lỗi TypeScript có sẵn ở `Sidebar.tsx` và `useLipSync.ts`, không phát sinh từ `RightSidebar.tsx`.
