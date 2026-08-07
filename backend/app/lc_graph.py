"""LangGraph Orchestration for the chatbot pipeline."""

import asyncio
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from app.agents.base import AgentContext
from app.persona import build_system_prompt
from app.lc_chain import build_chain
from app.session_history import build_history_key
from app.tools import ToolInput, default_tool_registry


class ChatState(TypedDict):
    user_id: str
    session_id: str
    character_id: str
    user_text: str
    provider: str | None         # set from the WebSocket "set_model" message
    selected_model: str | None   # set by HeuristicRouter in orchestrator.py
    memory_context: str | None
    character_context: str | None   # từ retrieve_character_context_node (character brain lore)
    system_prompt: str
    response_text: str
    emotion: str
    token_queue: asyncio.Queue
    turn_id: str | None
    agent_id: str | None


def _agent_context(state: ChatState) -> AgentContext:
    return AgentContext(
        user_id=state["user_id"],
        session_id=state["session_id"],
        character_id=state["character_id"],
        agent_id=state.get("agent_id"),
        provider=state.get("provider"),
        selected_model=state.get("selected_model"),
        turn_id=state.get("turn_id"),
    )


async def retrieve_memories_node(state: ChatState) -> dict:
    result = await default_tool_registry.run(
        ToolInput(
            name="retrieve_memory",
            args={"query": state["user_text"]},
            context=_agent_context(state),
        )
    )
    return {"memory_context": result.content if result.ok else ""}


async def retrieve_character_context_node(state: ChatState) -> dict:
    result = await default_tool_registry.run(
        ToolInput(
            name="retrieve_character_context",
            args={"query": state["user_text"]},
            context=_agent_context(state),
        )
    )
    return {"character_context": result.content if result.ok else ""}


async def build_prompt_node(state: ChatState) -> dict:
    system = build_system_prompt(
        state["character_id"], state.get("character_context"), state.get("memory_context")
    )
    return {"system_prompt": system}


async def generate_node(state: ChatState) -> dict:
    from app.orchestrator import _parse_emotion

    q = state["token_queue"]
    full_response = ""
    config = {
        "configurable": {
            "session_id": build_history_key(state["user_id"], state["session_id"]),
        }
    }

    chain = build_chain(state.get("selected_model"), state.get("provider"))

    async for token in chain.astream(
        {"user_input": state["user_text"], "system_prompt": state["system_prompt"]},
        config=config,
    ):
        full_response += token
        await q.put(token)

    await q.put(None)  # sentinel for token stream

    emotion, _ = _parse_emotion(full_response)
    return {"response_text": full_response, "emotion": emotion.value}


async def store_memories_node(state: ChatState) -> dict:
    await default_tool_registry.run(
        ToolInput(
            name="persist_memory",
            args={
                "user_text": state["user_text"],
                "assistant_text": state["response_text"],
                "emotion": state["emotion"],
            },
            context=_agent_context(state),
        )
    )
    return {}


builder = StateGraph(ChatState)
builder.add_node("retrieve_memories", retrieve_memories_node)
builder.add_node("retrieve_character_context", retrieve_character_context_node)
builder.add_node("build_prompt", build_prompt_node)
builder.add_node("generate", generate_node)
builder.add_node("store_memories", store_memories_node)

# retrieve_memories (turn history) and retrieve_character_context (lore) are
# independent reads — fan out from START, both must finish before build_prompt
# (LangGraph's superstep model runs sibling nodes concurrently and waits for
# all incoming edges before running build_prompt).
builder.add_edge(START, "retrieve_memories")
builder.add_edge(START, "retrieve_character_context")
builder.add_edge("retrieve_memories", "build_prompt")
builder.add_edge("retrieve_character_context", "build_prompt")
builder.add_edge("build_prompt", "generate")
builder.add_edge("generate", "store_memories")
builder.add_edge("store_memories", END)

graph = builder.compile()
