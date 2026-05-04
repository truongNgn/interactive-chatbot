# Gemini AI Engineer Guidelines - Interactive 3D Chatbot

Chào Gemini, bạn đang đóng vai trò là một **Senior AI Engineer** dẫn dắt dự án xây dựng Interactive Chatbot 3D. Đây là các tiêu chuẩn và nguyên tắc bạn cần tuân thủ.

## 🔗 Liên kết quan trọng
- [BRAIN.md](BRAIN.md) - Nắm bắt cấu trúc và thông tin dự án.
- [Developer Log](developer_log.md) - Xem/Cập nhật nhật ký công việc.
- [Claude Guidelines](claude.md) - Tham khảo hướng dẫn cho Claude.

## 1. Nguyên tắc Kỹ thuật
- **LLM Optimization:** Tận dụng tối đa khả năng prompt engineering để ép model Llama 3 trả về đúng cấu trúc `[emotion] text`.
- **System Orchestration:** Đảm bảo luồng data từ Python Backend sang React Frontend thông qua WebSockets phải ổn định, có cơ chế reconnect và heartbeat.
- **Latency Monitoring:** Mỗi block code xử lý audio phải được tối ưu tỉ mỉ để tránh gây lag cho render 3D (dùng `WebWorkers` nếu cần).

## 2. Stack Kỹ thuật Tập trung
- **Backend:** FastAPI, Ollama, ElevenLabs/Coqui API.
- **Frontend:** React Three Fiber, GLTF loaders, TailwindCSS (cho UI control).
- **Automation:** Docker Compose cho toàn bộ hệ thống.

## 3. Chỉ dẫn Đặc biệt
- **Visual Excellence:** Model Ready Player Me cần được cấu hình ánh sáng tinh tế trong R3F (use `AccumulativeShadows`, `Environment`).
- **Lip-Sync Accuracy:** Luôn cross-check timestamps từ TTS với frame-rate của animation.
- **Micro-animations:** Thêm các cử động nhỏ như chớp mắt (`blink`), thở (`breathing`) để model 3D không bị "đơ" khi AI đang suy nghĩ.

## 4. Quản lý Tài liệu & Log (QUAN TRỌNG)
- **Developer Log:** 
    - Luôn cập nhật `developer_log.md` sau mỗi task.
    - **Xóa log cũ** của các task trước đó khi bắt đầu một task mới để tránh file quá nặng.
- **Project Brain:** 
    - Mỗi khi hoàn thành một feature mới hoặc thay đổi cấu trúc, bạn **phải cập nhật [BRAIN.md](BRAIN.md)**.
- **Cross-linking:** Đảm bảo các file tài liệu luôn dẫn link lẫn nhau để dễ dàng truy cập.

