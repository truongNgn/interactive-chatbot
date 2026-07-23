"""
Character Persona manager (Stage 2 + multi-character roleplay upgrade).
"""
from app.character_registry import character_registry
from app.config import settings

EMOTION_RULES = """
CRITICAL INSTRUCTION — EMOTION TAGS:
For EVERY sentence you generate, you MUST prepend it with exactly one emotion tag from the following list:
[joy] [sad] [neutral] [thinking] [surprise] [anger]

Example:
[joy] Hello there! How can I help you today?
[thinking] Hmm, let me think about that.
[neutral] The capital of France is Paris.

Never output a sentence without an emotion tag at the beginning.
"""

def build_system_prompt(
    character_id: str | None = None,
    character_context: str | None = None,
    memory_context: str | None = None,
) -> str:
    parts = [build_persona_block(character_id), EMOTION_RULES]
    if character_context:
        # Lore comes before user memory — it defines WHO is speaking, which
        # should anchor the response before "what this user has said before".
        parts.append(character_context)
    if memory_context:
        parts.append(f"Relevant memories about the user:\n{memory_context}")
    return "\n\n".join(parts)


def build_persona_block(character_id: str | None = None) -> str:
    character = character_registry.get(character_id) if character_id else None

    if character:
        # Identity-level detail (backstory/personality) now comes from the
        # ingested character brain document via character_context — keep this
        # block to a short anchor line to avoid duplicating that content.
        return f"You are {character['display_name']}."

    # Fallback: no registry entry (unset/unknown character_id) — use the
    # single static persona from settings, same as before multi-character.
    parts = []
    if settings.character_name:
        parts.append(f"You are {settings.character_name}.")
    else:
        parts.append("You are a helpful AI assistant.")

    if settings.character_backstory:
        parts.append(settings.character_backstory)

    if settings.character_personality:
        parts.append(f"Personality: {settings.character_personality}")

    return "\n".join(parts)
