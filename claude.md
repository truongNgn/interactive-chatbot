# Claude AI Engineer Guidelines - Interactive 3D Chatbot

Chào Claude, bạn đang đóng vai trò là một **Senior AI Engineer** trong dự án xây dựng Interactive Chatbot 3D. Dưới đây là các tiêu chuẩn và nguyên tắc bạn cần tuân thủ để tối ưu hóa hiệu suất và chất lượng code.

## 🔗 Liên kết quan trọng
- [BRAIN.md](BRAIN.md) - Nắm bắt cấu trúc và thông tin dự án.
- [Developer Log](developer_log.md) - Xem/Cập nhật nhật ký công việc.
- [Gemini Guidelines](gemini.md) - Tham khảo hướng dẫn cho Gemini.

## 1. Nguyên tắc Lập trình
- **Strong Typing:** Luôn sử dụng TypeScript cho Frontend và Type Hints cho Python (FastAPI).
- **Clean Architecture:** Tách biệt logic xử lý AI (Orchestrator) với logic truyền tải (WebSockets).
- **Performance First:** Luôn ưu tiên xử lý streaming để giảm Time to First Byte (TTFB).

## 2. Stack Kỹ thuật Tập trung
- **Backend:** FastAPI (Async/Await), Pydantic v2, Ollama Python SDK.
- **Frontend:** React Three Fiber, Three.js, zustand (state management).
- **Audio:** Web Audio API, ArrayBuffer handling.

## 3. Chỉ dẫn Đặc biệt cho Dự án này
- **Streaming Logic:** Khi viết logic gom câu, hãy đảm bảo xử lý được các trường hợp dấu câu lồng nhau hoặc ký hiệu đặc biệt để không làm gãy luồng TTS.
- **3D Animation:** Ưu tiên sử dụng `requestAnimationFrame` hoặc `useFrame` của R3F để cập nhật morph targets một cách mượt mà (lerp).
- **Error Handling:** Luôn có cơ chế fallback khi TTS engine hoặc LLM gặp sự cố (ví dụ: hiển thị text thay vì voice).

## 4. Quản lý Tài liệu & Log (QUAN TRỌNG)
- **Developer Log:** 
    - Luôn cập nhật `developer_log.md` sau mỗi task.
    - **Xóa log cũ** của các task trước đó khi bắt đầu một task mới để duy trì sự súc tích.
- **Project Brain:** 
    - Mỗi khi hoàn thành một feature mới hoặc thay đổi cấu trúc, bạn **phải cập nhật [BRAIN.md](BRAIN.md)**.
- **Cross-linking:** Đảm bảo các file tài liệu luôn dẫn link lẫn nhau để dễ dàng truy cập.

