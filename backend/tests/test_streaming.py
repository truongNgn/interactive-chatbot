from app.models import Emotion
from app.orchestrator.streaming import _parse_emotion, flush_buffer, should_flush


def test_parse_emotion_tag() -> None:
    emotion, text = _parse_emotion("[thinking] Let me check.")
    assert emotion == Emotion.thinking
    assert text == "Let me check."


def test_flush_buffer_preserves_voice() -> None:
    chunk = flush_buffer("[joy] Hello!", voice="voice.wav")
    assert chunk is not None
    assert chunk.emotion == Emotion.joy
    assert chunk.text == "Hello!"
    assert chunk.voice == "voice.wav"


def test_should_flush_sentence_end() -> None:
    assert should_flush("Hello!", "!", is_first_chunk=True)
    assert not should_flush("short,", ",", is_first_chunk=False)
