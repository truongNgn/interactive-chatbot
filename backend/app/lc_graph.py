"""LangGraph Orchestration for the chatbot pipeline."""

import asyncio
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.memory_store import hybrid_retrieve
from app.memory_middleware import schedule_persist
from app.persona import build_system_prompt
from app.lc_chain import build_chain


class ChatState(TypedDict):
    user_id: str
    session_id: str
    user_text: str
    selected_model: str | None   # set by HeuristicRouter in orchestrator.py
    memory_context: str | None
    system_prompt: str
    response_text: str
    emotion: str
    token_queue: asyncio.Queue


async def retrieve_memories_node(state: ChatState) -> dict:
    context = await hybrid_retrieve(state["user_id"], state["user_text"])
    return {"memory_context": context}


async def build_prompt_node(state: ChatState) -> dict:
    system = build_system_prompt(state.get("memory_context"))
    return {"system_prompt": system}


async def generate_node(state: ChatState) -> dict:
    from app.orchestrator import _parse_emotion

    q = state["token_queue"]
    full_response = ""
    config = {"configurable": {"session_id": state["session_id"]}}

    chain = build_chain(state.get("selected_model"))

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
    schedule_persist(
        state["user_id"],
        state["session_id"],
        state["user_text"],
        state["response_text"],
        state["emotion"],
    )
    return {}


builder = StateGraph(ChatState)
builder.add_node("retrieve_memories", retrieve_memories_node)
builder.add_node("build_prompt", build_prompt_node)
builder.add_node("generate", generate_node)
builder.add_node("store_memories", store_memories_node)

builder.set_entry_point("retrieve_memories")
builder.add_edge("retrieve_memories", "build_prompt")
builder.add_edge("build_prompt", "generate")
builder.add_edge("generate", "store_memories")
builder.add_edge("store_memories", END)

graph = builder.compile()
