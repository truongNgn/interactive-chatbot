from enum import Enum
from pydantic import BaseModel, Field


class Emotion(str, Enum):
    joy = "joy"
    sad = "sad"
    neutral = "neutral"
    thinking = "thinking"
    surprise = "surprise"
    anger = "anger"


class SentenceChunk(BaseModel):
    text: str
    emotion: Emotion = Emotion.neutral


# --- WebSocket message types (client -> server) ---

class UserMessagePayload(BaseModel):
    type: str = "user_message"
    text: str


class InterruptPayload(BaseModel):
    type: str = "interrupt"


# --- WebSocket message types (server -> client) ---

class TextChunkPayload(BaseModel):
    """Sent immediately when a sentence is buffered, before TTS (Stage 2)."""
    type: str = "text_chunk"
    text: str
    emotion: Emotion


class VisemeEntry(BaseModel):
    """One Rhubarb mouth-cue: time range + phoneme value (A-H, X)."""
    start: float
    end: float
    value: str


class AudioChunkPayload(BaseModel):
    """Sent after TTS synthesis. Contains base64-encoded audio + viseme keyframes."""
    type: str = "audio_chunk"
    text: str
    emotion: Emotion
    audio_base64: str
    duration_ms: int = 0
    visemes: list[VisemeEntry] = Field(default_factory=list)


class ErrorPayload(BaseModel):
    type: str = "error"
    message: str


class DonePayload(BaseModel):
    type: str = "done"
