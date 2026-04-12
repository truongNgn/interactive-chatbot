# Kế hoạch Triển khai (Implementation Plan): Hệ thống Interactive Voice Chatbot với 3D Avatar

Tài liệu này mô tả kiến trúc kỹ thuật và lộ trình chi tiết để xây dựng hệ thống chatbot tương tác bằng giọng nói thời gian thực, kết hợp hiển thị nhân vật 3D (Avatar) có khả năng hót nhép (lip-sync) và biểu cảm khuôn mặt bám sát ngữ cảnh (context-aware emotions).

**Công nghệ cốt lõi:**
- **Backend:** Python, FastAPI, WebSockets, Llama 3 (Ollama), Coqui XTTSv2 / ElevenLabs.
- **Frontend:** TypeScript, React, React Three Fiber (R3F), Drei.
- **Xử lý Audio/Model:** Rhubarb Lip Sync, GLTF/GLB (Ready Player Me).
- **Triển khai:** Docker, Docker Compose.

---

## Kiến trúc Hệ thống Tổng quan

Sử dụng kiến trúc Client-Server thông qua WebSockets để đảm bảo **độ trễ thấp (low-latency)** toàn trình (End-to-End).

1. **Frontend (React/R3F):** Xử lý UI, render 3D model, thu bắt giọng nói qua Micro, nhận audio streams & visemes để chạy animation.
2. **Backend (FastAPI Orchestrator):** Điều phối luồng xử lý: STT (Speech-to-Text) -> LLM (Sinh Text + Emotion) -> TTS (Text-to-Speech) -> Phân tích Visemes -> Đẩy Stream (Audio + Animation data) qua WebSocket.

---

## Lộ trình Chi tiết (5 Giai đoạn)

### Stage 1: Xây dựng AI Core & Luồng Streaming (Backend)

**Mục tiêu:** Hệ thống Llama 3 có thể trả về câu trả lời phân đoạn theo thời gian thực (streaming) và gán nhãn cảm xúc từng đoạn.

*   **Setup Orchestrator (FastAPI):**
    *   Khởi tạo FastAPI app. Cài đặt các endpoint WebSocket để chấp nhận kết nối liên tục từ Client.
*   **Tích hợp LLM (Ollama + Llama 3):**
    *   Sử dụng thư viện `ollama-python` để giao tiếp với local instance Llama 3:8B.
*   **Prompt Engineering (Gán nhãn cảm xúc):**
    *   Thiết kế System Prompt bắt buộc model phải suy luận cảm xúc *trước* khi trả lời và bọc trong tag.
    *   *Ví dụ System Prompt:* `You are a helpful and expressive AI assistant. For every sentence you generate, prepend it with exactly one emotion tag from the following list: [joy], [sad], [neutral], [thinking], [surprise], [anger]. Example: [joy] Hello there! How can I help you today?`
*   **Sentence-Buffering & Streaming Logic:**
    *   Đọc token stream từ Ollama. Thay vì gửi từng token (không thể TTS), hãy dùng Regex/Logic để gom các token thành các câu hoặc mệnh đề hoàn chỉnh (bắt các dấu phân cách `.` `?` `!` `,`).
    *   Ngay khi có một câu hoàn chỉnh, bóc tách nhãn cảm xúc và đẩy cấu trúc dữ liệu `{ text, emotion }` vào Queue của Stage 2.

### Stage 2: Tích hợp Text-to-Speech (TTS) & Voice Cloning

**Mục tiêu:** Sinh audio realtime cho từng câu văn được buffer ở Stage 1 với chất lượng giọng nói tự nhiên.

*   **Lựa chọn engine TTS:**
    *   *Tùy chọn Local:* Cài đặt **Coqui XTTSv2**. Ưu điểm là miễn phí, cấu hình clone giọng tốt. Yêu cầu GPU mạnh.
    *   *Tùy chọn Cloud (Khuyến nghị cho MVP ban đầu):* **ElevenLabs API** (hỗ trợ WebSocket streaming cho độ trễ < 400ms).
*   **Xử lý Audio Chunking:**
    *   Lấy JSON `{ text, emotion }` từ Queue. Sử dụng TTS để chuyển `text` thành mảng byte (`audio bytes`).
    *   *Lưu ý:* Map `emotion` sang các preset giọng của TTS (nếu TTS engine hỗ trợ, VD: nói nhanh/cao giọng khi `[joy]`).
*   **Giao thức truyền tải (WebSocket Payload):**
    *   Gửi payload xuống Frontend theo định dạng JSON nhị phân hỗn hợp (Base64) hoặc ArrayBuffer:
        ```json
        {
          "type": "audio_chunk",
          "emotion": "joy",
          "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA...",
          "visemes": [...] // Xem Stage 4
        }
        ```

### Stage 3: Setup 3D Frontend (React + R3F)

**Mục tiêu:** Render nhân vật 3D mượt mà trên trình duyệt, sẵn sàng xử lý dữ liệu từ Backend.

*   **Chuẩn bị Resource (3D Model):**
    *   Sử dụng [Ready Player Me](https://readyplayer.me) (hoặc VRoid) tạo một Avatar định dạng `.glb`. **Yêu cầu bắt buộc:** Model phải có sẵn hệ thống xương hàm và Blendshapes theo chuẩn ARKit (hoặc chuẩn hình thái nhận diện viseme cơ bản: A, E, I, O, U, MBP, v.v.).
*   **Khởi tạo Môi trường (R3F):**
    *   Setup `<Canvas>` của `@react-three/fiber`. Sử dụng `@react-three/drei` (như `useGLTF`, `Environment`, `ContactShadows`) để tạo cảnh quan, ánh sáng PBR và load model nhanh chóng.
*   **Audio Queue Management (Frontend):**
    *   Tạo một `AudioContext` để phát âm thanh.
    *   Khi nhận dữ liệu WebSocket từ Backend, không phát ngay nếu đang có audio khác đang chạy. Đưa vào một mảng `Queue`.
    *   Xây dựng Hook `useAudioQueue` để tự động pop audio chunk và phát liên tục, tránh gián đoạn giữa các câu.

### Stage 4: Animation & Khớp khẩu hình (Lip-sync)

**Mục tiêu:** Môi nhân vật mấp máy chính xác theo âm thanh và biểu cảm khuôn mặt thay đổi theo nhãn `emotion`.

*   **Sinh Visemes (Backend):**
    *   Sử dụng thư viện Rhubarb Lip Sync (dạng CLI tool hoặc wrapper) ngay trên Backend.
    *   Ngay khi TTS tạo xong `audio_bytes` (Stage 2), đưa audio này vào Rhubarb phân tích để lấy ra danh sách các `visemes` (miệng mở chữ A, chữ O, ngậm miệng...) tương ứng với các mốc thời gian (timestamp).
    *   Đóng gói chuỗi thời gian này gửi kèm payload xuống Frontend.
*   **Thực thi Lip-sync trên R3F (Frontend):**
    *   Trong `useFrame` của R3F (hàm chạy 60 khung hình/giây), lấy `currentTime` của thẻ Audio đang phát.
    *   Dò trong mảng visemes xem ở thời điểm `currentTime` này, miệng đang ở khẩu hình nào.
    *   Sử dụng thư viện nội suy (Lerp) kết hợp thay đổi tham số `morphTargetInfluences` (ví dụ: `nodes.Head.morphTargetInfluences[indexOfVisemeA] = 1`) để tạo hiệu ứng miệng chuyển động mượt mà.
*   **Xử lý Emotion Blendshapes (Biểu cảm):**
    *   Đọc trường `emotion` nhận từ payload của câu hiện tại.
    *   Ánh xạ (Mapping) emotion string với các blendshapes hoặc Animations:
        *   `[joy]`: Tăng thông số `smile`, nhướng lông mày.
        *   `[thinking]`: Mắt liếc nhẹ lên trên, môi hơi mím (`mouthPucker`), kích hoạt animation tay đưa lên mặt.
        *   Sử dụng thư viện như `framer-motion-3d` hoặc lerp thủ công để chuyển đổi trạng thái cảm xúc từ từ, tránh giật cục.

### Stage 5: Tối ưu hóa & Đóng gói (Dockerization)

**Mục tiêu:** Hệ thống phản hồi tức thì, hỗ trợ can thiệp luồng nói (Interruption) và dễ dàng triển khai.

*   **Cơ chế Ngắt lời (Interruption Handle):**
    *   Frontend triển khai VAD (Voice Activity Detection - ví dụ dùng `hark.js` hoặc Web Audio API cơ bản) để phát hiện khi người dùng đột ngột nói (trong lúc AI đang nói).
    *   Gửi ngay một WebSocket event `{"type": "interrupt"}` tới Backend.
    *   Backend nhận tín hiệu -> **Kill/Cancel task** của LLM và TTS đang sinh dở -> Gửi tín hiệu `{"type": "clear_queue"}` về Frontend để Frontend dừng phát audio hiện tại và reset khuôn mặt. -> Lắng nghe mệnh lệnh nhận định mới của người dùng.
*   **Tối ưu Latency (TTFB - Time to First Byte):**
    *   Tinh chỉnh Sentence-Buffering: Nếu câu đầu tiên dài, thử trả về các đoạn ngắn ("Yes,", "Well,") sớm hơn để TTS chạy ngay tạo cảm giác realtime.
*   **Đóng gói bằng Docker:**
    *   Sử dụng `docker-compose.yml` gồm 3 services chính:
        1.  `frontend`: Cung cấp React web tĩnh (Nginx/Node).
        2.  `backend`: Chứa FastAPI, Rhubarb bin, chạy Gunicorn.
        3.  `ollama`: Pull image `ollama/ollama`, thiết lập volume mount để không cẩn pull lại models `llama3` mỗi lần restart.

---

> [!TIP]
> **Khởi điểm với Minimum Viable Product (MVP):**
> Trong Sprint đầu tiên, hãy tạm dùng ElevenLabs (hoặc OpenAI TTS API) cho âm thanh và bỏ qua Rhubarb phân tích. Dùng hàm phân tích tín hiệu âm thanh thô (cường độ âm lượng) ngay tại Frontend để mấp máy môi đơn giản. Khi giao tiếp WebSocket ổn định, hãy chuyển sang XTTS và Rhubarb để tăng tính chân thực.

## User Review Required

> [!IMPORTANT]
> Trước khi bắt tay vào code, bạn cần xác nhận việc sử dụng giải pháp Local TTS (đòi hỏi máy cấu hình VRAM mạnh) hay Cloud TTS (trả phí nhỏ nhưng dễ setup) cho MVP ban đầu. Ngoài ra có thể có issue với Rhubarb Lip Sync khi wrap với tiếng Việt (Visemes có thể không thực sự khớp hoàn toàn 100% so với tiếng Anh). Bạn đồng ý duy trì chứ?
