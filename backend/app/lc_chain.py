"""LangChain chain: provider LLM + ChatPromptTemplate + session history."""

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from app.config import settings

# 2. Prompt template — system_prompt được inject động từ lc_graph.py (build_system_prompt)
#    bao gồm: persona + emotion_rules + memory_context (nếu có)
prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    MessagesPlaceholder("history"),
    ("human", "{user_input}"),
])

# In-memory session store (shared across all chain instances)
_session_store: dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
    return _session_store[session_id]


def _resolve_model(model: str | None, provider: str) -> str:
    if model:
        return model
    if provider == "vllm":
        return settings.vllm_large_model
    return settings.ollama_large_model


def build_chain(model: str | None = None) -> RunnableWithMessageHistory:
    """
    Build a RunnableWithMessageHistory chain for the selected provider/model.

    Pass model=None to use the provider's default large model from config.
    Chains are cached per provider and model to avoid recreating clients every turn.
    """
    provider = settings.llm_provider.lower().strip()
    resolved = _resolve_model(model, provider)
    cache_key = f"{provider}:{resolved}"
    if cache_key not in _chain_cache:
        if provider == "vllm":
            llm = ChatOpenAI(
                model=resolved,
                base_url=settings.vllm_base_url,
                api_key="not-needed",
                streaming=True,
            )
        else:
            llm = ChatOllama(
                model=resolved,
                base_url=settings.ollama_host,
                keep_alive=settings.ollama_keep_alive,
            )
        base_chain = prompt | llm | StrOutputParser()
        _chain_cache[cache_key] = RunnableWithMessageHistory(
            base_chain,
            get_session_history,
            input_messages_key="user_input",
            history_messages_key="history",
        )
    return _chain_cache[cache_key]


# Cache: provider:model_name → RunnableWithMessageHistory
_chain_cache: dict[str, RunnableWithMessageHistory] = {}

# Backward-compatible singleton — used by code that imports `chain` directly
chain = build_chain()
