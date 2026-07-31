"""Sentence buffering helpers used by the turn orchestrator."""

from __future__ import annotations

import re

from app.models import Emotion, SentenceChunk

_EMOTION_TAG_RE = re.compile(
    r"^\s*\[(joy|sad|neutral|thinking|surprise|anger)\]\s*",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?。？！]+")
_CLAUSE_END_RE = re.compile(r"[,;\n—\-–]+")

_FIRST_CLAUSE_LEN = 15
_NORMAL_CLAUSE_LEN = 80


def _parse_emotion(text: str) -> tuple[Emotion, str]:
    match = _EMOTION_TAG_RE.match(text)
    if match:
        emotion_str = match.group(1).lower()
        clean = text[match.end():].strip()
        try:
            return Emotion(emotion_str), clean
        except ValueError:
            pass
    return Emotion.neutral, text.strip()


def _should_flush(buffer: str, char: str, is_first_chunk: bool) -> bool:
    return should_flush(buffer, char, is_first_chunk)


def should_flush(buffer: str, char: str, is_first_chunk: bool) -> bool:
    if _SENTENCE_END_RE.search(char):
        return True

    if _CLAUSE_END_RE.search(char):
        threshold = _FIRST_CLAUSE_LEN if is_first_chunk else _NORMAL_CLAUSE_LEN
        return len(buffer) >= threshold

    return False


def flush_buffer(raw: str, voice: str | None = None) -> SentenceChunk | None:
    emotion, text = _parse_emotion(raw)
    text = text.strip()
    if not text:
        return None
    return SentenceChunk(text=text, emotion=emotion, voice=voice)
