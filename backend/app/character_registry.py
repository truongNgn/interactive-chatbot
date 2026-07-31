"""Character registry fallback for multi-character chat metadata.

The original registry implementation is not present in this checkout. This
module keeps the public API used by the gateway/persona code stable while
loading character metadata from docs/characters/characters.json when available.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "docs" / "characters" / "characters.json"


@dataclass(frozen=True)
class Character:
    id: str
    display_name: str
    voice: str | None = None
    avatar: str | None = None
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "voice": self.voice,
            "avatar": self.avatar,
            "description": self.description,
            **self.metadata,
        }


class CharacterRegistry:
    def __init__(self, registry_path: Path = DEFAULT_REGISTRY_PATH) -> None:
        self._registry_path = registry_path
        self._characters = self._load_characters()

    def get(self, character_id: str | None) -> dict[str, Any] | None:
        if not character_id:
            return None
        character = self._characters.get(character_id)
        return character.public_dict() if character else None

    def list_public(self) -> list[dict[str, Any]]:
        return [character.public_dict() for character in self._characters.values()]

    def _load_characters(self) -> dict[str, Character]:
        loaded = self._load_from_json()
        if loaded:
            return loaded

        fallback = Character(
            id=settings.default_character_id,
            display_name=settings.character_name or settings.default_character_id.title(),
            voice=None,
            avatar=None,
            description=settings.character_persona,
        )
        logger.warning(
            "Character registry file not found or empty at %s; using fallback character '%s'.",
            self._registry_path,
            fallback.id,
        )
        return {fallback.id: fallback}

    def _load_from_json(self) -> dict[str, Character]:
        if not self._registry_path.exists():
            return {}

        try:
            raw = json.loads(self._registry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read character registry %s: %s", self._registry_path, exc)
            return {}

        items = raw.get("characters", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            logger.warning("Character registry %s must contain a list.", self._registry_path)
            return {}

        characters: dict[str, Character] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            character_id = str(item.get("id", "")).strip()
            if not character_id:
                continue
            metadata = {
                key: value
                for key, value in item.items()
                if key not in {"id", "display_name", "name", "voice", "avatar", "description"}
            }
            characters[character_id] = Character(
                id=character_id,
                display_name=str(item.get("display_name") or item.get("name") or character_id),
                voice=item.get("voice"),
                avatar=item.get("avatar"),
                description=str(item.get("description", "")),
                metadata=metadata,
            )

        return characters


character_registry = CharacterRegistry()
