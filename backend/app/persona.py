"""
Character Persona manager (Stage 2).
"""
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

def build_system_prompt(memory_context: str | None = None) -> str:
    parts = [build_persona_block(), EMOTION_RULES]
    if memory_context:
        parts.append(f"Relevant memories about the user:\n{memory_context}")
    return "\n\n".join(parts)

def build_persona_block() -> str:
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
