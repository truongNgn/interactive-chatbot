from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM Provider selection: "ollama" | "deepseek"
    llm_provider: str = "ollama"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:latest"       # legacy alias — dùng ollama_large_model
    ollama_large_model: str = "llama3.1:latest"
    ollama_small_model: str = "qwen2.5:1.5b"
    router_enabled: bool = True

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" — default voice
    elevenlabs_model_id: str = "eleven_turbo_v2_5"
    elevenlabs_output_format: str = "mp3_44100_128"

    # Coqui XTTS-v2 (local voice cloning)
    xtts_speaker_wav: str = ""          # path tới file giọng mẫu (.wav)
    xtts_language: str = "vi"           # "vi" hoặc "en", xem danh sách: https://docs.coqui.ai
    xtts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"

    # Rhubarb Lip-Sync (Stage 4)
    # Set to the path of rhubarb.exe (Windows) or rhubarb binary (Linux/Mac).
    # Leave empty to disable lip-sync (visemes will be []).
    rhubarb_path: str = ""

    # Session / History (Stage 1)
    max_history_turns: int = 20          # số lượt hội thoại tối đa giữ trong memory

    # Character Persona (Stage 2)
    character_name: str = "Aria"
    character_persona: str = "a warm, expressive AI companion who enjoys meaningful conversations"
    character_backstory: str = ""        # ví dụ: "grew up in a coastal town, loves music"
    character_personality: str = ""     # ví dụ: "curious, empathetic, occasionally witty"

    # Long-term Memory — ChromaDB (Stage 3)
    memory_enabled: bool = True
    chroma_path: str = "./chroma_data"
    embedding_model: str = "nomic-embed-text"
    memory_retrieval_count: int = 5
    memory_dedup_threshold: float = 0.95
    memory_recency_weight: float = 0.3

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # bỏ qua env vars không khai báo trong Settings
    )


settings = Settings()
