from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM Provider selection: "ollama" | "deepseek"
    llm_provider: str = "ollama"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"

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
