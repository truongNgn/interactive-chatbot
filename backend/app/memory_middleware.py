import asyncio
import logging
import re

from app.memory_store import retrieve_memories, store_turn, store_fact

logger = logging.getLogger(__name__)

# Patterns: (fact_type, [regex_list])
# Each regex must have exactly one capture group — the fact value.
_FACT_PATTERNS: list[tuple[str, list[str]]] = [
    ("name", [
        r"my name is ([A-Za-z][A-Za-z\s]{1,30}?)(?:\s*[,\.!?]|$)",
        r"call me ([A-Za-z][A-Za-z\s]{1,20}?)(?:\s*[,\.!?]|$)",
        r"i(?:'m| am) ([A-Za-z][A-Za-z\s]{1,30}?),\s*your",  # "I am Truong, your best friend"
        r"name(?:'s| is) ([A-Za-z][A-Za-z\s]{1,20}?)(?:\s*[,\.!?]|$)",
    ]),
    ("job", [
        r"i work (?:as|at) (?:a |an )?([A-Za-z][A-Za-z\s]{1,40}?)(?:\s*[,\.!?]|$)",
        r"my (?:job|occupation|profession) is ([A-Za-z][A-Za-z\s]{1,40}?)(?:\s*[,\.!?]|$)",
        r"i(?:'m| am) (?:a |an )([A-Za-z][A-Za-z\s]{1,30}?) (?:by profession|at |working)",
    ]),
    ("interest", [
        r"i (?:really )?love ([A-Za-z][A-Za-z\s]{1,40}?)(?:\s*[,\.!?]|$)",
        r"i (?:really )?enjoy ([A-Za-z][A-Za-z\s]{1,40}?)(?:\s*[,\.!?]|$)",
        r"my (?:favorite|favourite)(?: thing| hobby)? is ([A-Za-z][A-Za-z\s]{1,40}?)(?:\s*[,\.!?]|$)",
    ]),
    ("location", [
        r"i (?:live|am) (?:in|from) ([A-Za-z][A-Za-z\s,]{1,40}?)(?:\s*[,\.!?]|$)",
        r"i(?:'m| am) (?:from|based in) ([A-Za-z][A-Za-z\s]{1,40}?)(?:\s*[,\.!?]|$)",
    ]),
]


def _extract_facts(text: str) -> list[tuple[str, str]]:
    """Return list of (fact_type, fact_value) extracted from user message."""
    found: list[tuple[str, str]] = []
    lower = text.lower().strip()
    for fact_type, patterns in _FACT_PATTERNS:
        for pattern in patterns:
            m = re.search(pattern, lower, re.IGNORECASE)
            if m:
                value = m.group(1).strip().title()
                if value:
                    found.append((fact_type, value))
                break  # one match per fact_type is enough
    return found


async def enrich_with_memory(user_id: str, query: str) -> str | None:
    return await retrieve_memories(user_id, query)


def schedule_persist(user_id: str, session_id: str, user_text: str, assistant_text: str, emotion: str) -> None:
    asyncio.create_task(_persist(user_id, session_id, user_text, assistant_text, emotion))


async def _persist(user_id: str, session_id: str, user_text: str, assistant_text: str, emotion: str):
    # Store raw conversation turns
    await store_turn(user_id, session_id, "user", user_text, "neutral")
    await store_turn(user_id, session_id, "assistant", assistant_text, emotion)

    # Extract and store structured facts from user message
    facts = _extract_facts(user_text)
    for fact_type, fact_value in facts:
        await store_fact(user_id, fact_type, fact_value)
        logger.info("Extracted fact [%s] = %s", fact_type, fact_value)
