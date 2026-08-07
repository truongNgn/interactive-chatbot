"""LangChain chain: provider LLM + ChatPromptTemplate + session history."""

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from app.config import settings
from app.session_history import get_session_history

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# 2. Prompt template — system_prompt được inject động từ lc_graph.py (build_system_prompt)
#    bao gồm: persona + emotion_rules + memory_context (nếu có)
prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    MessagesPlaceholder("history"),
    ("human", "{user_input}"),
])


def normalize_provider(provider: str | None = None) -> str:
    """Provider dùng cho lượt chat hiện tại; None → giá trị trong .env."""
    return (provider or settings.llm_provider).lower().strip()


def _resolve_model(model: str | None, provider: str) -> str:
    if model:
        return model
    if provider == "vllm":
        return settings.vllm_large_model
    if provider == "gemini":
        return settings.gemini_model or "gemini-2.5-flash"
    if provider == "deepseek":
        return settings.deepseek_model
    if provider == "qwen":
        return settings.ollama_small_model
    return settings.ollama_large_model


def resolve_router_models(provider: str | None = None) -> tuple[str, str]:
    """
    Cặp (large_model, small_model) mà HeuristicRouter được phép chọn.

    Provider chỉ cấu hình một model (deepseek, gemini, qwen) thì hai giá trị
    bằng nhau — router vẫn chạy nhưng không đổi model.
    """
    resolved_provider = normalize_provider(provider)
    if resolved_provider == "vllm":
        return settings.vllm_large_model, settings.vllm_small_model
    if resolved_provider in ("ollama", ""):
        return settings.ollama_large_model, settings.ollama_small_model
    single = _resolve_model(None, resolved_provider)
    return single, single


def _build_llm(provider: str, model: str) -> BaseChatModel:
    """Chat model của LangChain cho provider — mọi nhánh đều được LangSmith trace."""
    if provider == "vllm":
        return ChatOpenAI(
            model=model,
            base_url=settings.vllm_base_url,
            api_key="not-needed",
            streaming=True,
        )
    if provider == "deepseek":
        return ChatOpenAI(
            model=model,
            base_url=DEEPSEEK_BASE_URL,
            api_key=settings.deepseek_api_key,
            streaming=True,
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.gemini_api_key,
            streaming=True,
        )
    return ChatOllama(
        model=model,
        base_url=settings.ollama_host,
        keep_alive=settings.ollama_keep_alive,
    )


def build_chain(
    model: str | None = None,
    provider: str | None = None,
) -> RunnableWithMessageHistory:
    """
    Build a RunnableWithMessageHistory chain for the selected provider/model.

    Pass provider=None to use LLM_PROVIDER from .env, model=None to use that
    provider's default large model. Chains are cached per provider and model to
    avoid recreating clients every turn.
    """
    resolved_provider = normalize_provider(provider)
    resolved_model = _resolve_model(model, resolved_provider)
    cache_key = f"{resolved_provider}:{resolved_model}"
    if cache_key not in _chain_cache:
        base_chain = prompt | _build_llm(resolved_provider, resolved_model) | StrOutputParser()
        _chain_cache[cache_key] = RunnableWithMessageHistory(
            base_chain,
            get_session_history,
            input_messages_key="user_input",
            history_messages_key="history",
        )
    return _chain_cache[cache_key]


# Cache: provider:model_name → RunnableWithMessageHistory
_chain_cache: dict[str, RunnableWithMessageHistory] = {}


def __getattr__(name: str):
    """
    Backward-compatible singleton `chain`, dựng lazy ở lần truy cập đầu tiên.

    Dựng eager lúc import khiến một provider cấu hình sai làm hỏng cả
    `import app.lc_graph`, và khi đó `graph.ainvoke()` không bao giờ chạy nên
    LangSmith không nhận được run nào. Lazy thì lỗi nổ trong generate_node và
    vẫn được trace lại dưới dạng run lỗi.
    """
    if name == "chain":
        return build_chain()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
