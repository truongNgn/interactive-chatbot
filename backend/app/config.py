import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_ROOT / ".env"

# LangSmith auto-tracing reads os.environ directly. BaseSettings parses .env
# into the settings object, but it does not export unknown keys for LangChain.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    # LLM Provider selection: "ollama" | "vllm" | "deepseek" | "gemini"
    llm_provider: str = "ollama"

    # TTS Provider selection: "elevenlabs" | "google-cloud" | "xtts" | ""
    tts_provider: str = ""

    # vLLM OpenAI-compatible server
    vllm_base_url: str = "http://localhost:8080/v1"
    vllm_large_model: str = "Meta-Llama-3.1-8B-Instruct-Q4_K_M"
    vllm_small_model: str = "Meta-Llama-3.1-8B-Instruct-Q4_K_M"
 
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:latest"       # legacy alias — dùng ollama_large_model
    ollama_large_model: str = "llama3.1:latest"
    ollama_small_model: str = "qwen2.5:1.5b"
    ollama_keep_alive: str = "30m"
    router_enabled: bool = True
    warmup_on_startup: bool = True
    warmup_blocking: bool = False
    warmup_timeout_seconds: float = 180.0

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" — default voice
    elevenlabs_model_id: str = "eleven_turbo_v2_5"
    elevenlabs_output_format: str = "mp3_44100_128"

    # Coqui XTTS-v2 (local voice cloning)
    xtts_speaker_wav: str = ""          # path tới file giọng mẫu (.wav)
    xtts_language: str = "vi"           # "vi" hoặc "en", xem danh sách: https://docs.coqui.ai
    xtts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"

    # Google Cloud TTS
    google_tts_voice_name: str = "vi-VN-Neural2-A"
    google_tts_language_code: str = "vi-VN"

    # Speech-to-Text (mic input Stage 3)
    stt_enabled: bool = False
    stt_provider: str = "faster-whisper"   # "faster-whisper" | "openai" | "none"
    stt_model: str = "base"                # faster-whisper: tiny/base/small/... | openai: whisper-1/gpt-4o-mini-transcribe
    stt_language: str = "vi"               # "vi" | "en" | "" for auto-detect
    stt_device: str = "cuda"               # "cuda" | "cpu"
    stt_compute_type: str = "float16"      # "float16" | "int8" | "float32"
    stt_max_file_mb: int = 10
    stt_max_duration_seconds: int = 60

    # Rhubarb Lip-Sync (Stage 4)
    # Set to the path of rhubarb.exe (Windows) or rhubarb binary (Linux/Mac).
    # Leave empty to disable lip-sync (visemes will be []).
    rhubarb_path: str = ""

    # Session / History (Stage 1)
    max_history_turns: int = 20          # số lượt hội thoại tối đa giữ trong memory

    # Character Persona (Stage 2) — fallback khi không tìm thấy nhân vật trong registry
    character_name: str = "Aria"
    character_persona: str = "a warm, expressive AI companion who enjoys meaningful conversations"
    character_backstory: str = ""        # ví dụ: "grew up in a coastal town, loves music"
    character_personality: str = ""     # ví dụ: "curious, empathetic, occasionally witty"

    # Character Roleplay — multi-character brain (Upgrade: character_brain plan)
    default_character_id: str = "luna"
    lore_data_path: str = "./lore_data"        # nơi lưu parent store (JSON)
    lore_top_k: int = 4
    lore_chunk_threshold_words: int = 3000     # Tier 2 threshold
    lore_chunk_size_chars: int = 1500
    lore_chunk_overlap_chars: int = 200

    # Long-term Memory — ChromaDB (Stage 3)
    memory_enabled: bool = True
    memory_fast_path_enabled: bool = True
    chroma_path: str = "./chroma_data"
    embedding_model: str = "nomic-embed-text"
    memory_retrieval_count: int = 5
    memory_dedup_threshold: float = 0.95
    memory_recency_weight: float = 0.3
    memory_rrf_k: int = 60
    memory_dense_weight: float = 1.0
    memory_sparse_weight: float = 1.5
    memory_dense_overfetch_multiplier: int = 2

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    log_level: str = "INFO"

    # Production hardening (Stage 7)
    # Authentication is always required: /ws/chat and all per-user REST
    # endpoints reject requests without a valid token (see app/auth.py).
    auth_token_secret: str = "change-me-dev-secret"
    auth_token_expire_minutes: int = 1440
    auth_dev_user_id: str = "dev_user"
    max_ws_message_bytes: int = 32768
    max_rest_request_bytes: int = 1048576
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    ws_rate_limit_messages: int = 60
    ws_rate_limit_window_seconds: int = 60
    session_backend: str = "file"  # "file" | "memory"
    session_history_path: str = "./data/session_history"
    database_url: str = "postgresql+asyncpg://chatbot:chatbot@postgres:5432/chatbot"
    database_auto_create: bool = True
    google_client_id: str = ""

    # LangSmith Observability
    # Keep both modern LANGSMITH_* and legacy LANGCHAIN_* names so older docs
    # and newer SDKs work from the same .env file.
    langsmith_tracing: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = ""
    langsmith_endpoint: str = ""
    langchain_tracing_v2: str = ""
    langchain_api_key: str = ""
    langchain_project: str = ""
    langchain_endpoint: str = ""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # bỏ qua env vars không khai báo trong Settings
    )


settings = Settings()


def _set_env_alias(primary: str, *fallbacks: str) -> None:
    if os.getenv(primary):
        return
    for name in fallbacks:
        value = os.getenv(name)
        if value:
            os.environ[primary] = value
            return


def configure_langsmith_environment() -> None:
    """
    Normalize LangSmith env vars for both legacy LangChain and current SDKs.

    This must run before LangChain/LangGraph modules create runnables because
    LangSmith caches environment configuration during import/use.
    """
    _set_env_alias("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2")
    _set_env_alias("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")
    _set_env_alias("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT")
    _set_env_alias("LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT")

    _set_env_alias("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING")
    _set_env_alias("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY")
    _set_env_alias("LANGCHAIN_PROJECT", "LANGSMITH_PROJECT")
    _set_env_alias("LANGCHAIN_ENDPOINT", "LANGSMITH_ENDPOINT")


configure_langsmith_environment()
