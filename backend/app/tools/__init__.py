"""Tool registry exports and default tool wiring."""

from app.tools.base import BaseTool, ToolInput, ToolResult
from app.tools.lipsync import GenerateVisemesTool
from app.tools.memory import PersistMemoryTool
from app.tools.registry import ToolRegistry
from app.tools.retrieval import RetrieveCharacterContextTool, RetrieveMemoryTool
from app.tools.speech import SynthesizeSpeechTool, TranscribeAudioTool

default_tool_registry = ToolRegistry()
default_tool_registry.register(RetrieveMemoryTool())
default_tool_registry.register(RetrieveCharacterContextTool())
default_tool_registry.register(PersistMemoryTool())
default_tool_registry.register(SynthesizeSpeechTool())
default_tool_registry.register(GenerateVisemesTool())
default_tool_registry.register(TranscribeAudioTool())

__all__ = [
    "BaseTool",
    "GenerateVisemesTool",
    "PersistMemoryTool",
    "RetrieveCharacterContextTool",
    "RetrieveMemoryTool",
    "SynthesizeSpeechTool",
    "ToolInput",
    "ToolRegistry",
    "ToolResult",
    "TranscribeAudioTool",
    "default_tool_registry",
]
