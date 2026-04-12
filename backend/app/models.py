from enum import Enum
from pydantic import BaseModel


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


class AudioChunkPayload(BaseModel):
    """
    Sent after TTS synthesis. Contains base64-encoded audio + metadata.
    visemes: placeholder list — will be populated by Rhubarb in Stage 4.
    audio_base64: empty string when TTS is not configured (text-only fallback).
    """
    type: str = "audio_chunk"
    text: str
    emotion: Emotion
    audio_base64: str
    duration_ms: int = 0          # filled in Stage 4 from audio metadata
    visemes: list = []            # filled in Stage 4 by Rhubarb


class ErrorPayload(BaseModel):
    type: str = "error"
    message: str


class DonePayload(BaseModel):
    type: str = "done"
