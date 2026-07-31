"""Orchestrator compatibility exports.

Stage 2 turns the old single `orchestrator.py` module into a package while
keeping existing imports such as `from app.orchestrator import Orchestrator`.
"""

from app.orchestrator.legacy import Orchestrator, sentence_stream
from app.orchestrator.streaming import _parse_emotion, _should_flush
from app.orchestrator.turn_orchestrator import TurnOrchestrator

__all__ = [
    "Orchestrator",
    "TurnOrchestrator",
    "_parse_emotion",
    "_should_flush",
    "sentence_stream",
]
