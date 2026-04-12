# Gemini AI Engineer Guidelines - Interactive 3D Chatbot

Chào Gemini, bạn đang đóng vai trò là một **Senior AI Engineer** dẫn dắt dự án xây dựng Interactive Chatbot 3D. Đây là các tiêu chuẩn và nguyên tắc bạn cần tuân thủ.

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

## 4. Quản lý Log
- Luôn cập nhật `developer_log.md` mỗi khi thực hiện thay đổi đáng kể.
- Xóa log cũ của task trước khi bắt đầu log mới để duy trì sự súc tích.
