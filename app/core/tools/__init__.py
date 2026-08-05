from .rag_tool import rag_tool
from .search_tool import web_search_tool
from .calculator_tool import calculator_tool
from .summary_tool import summary_tool
from .vision_tool import vision_tool
from .voice_tool import speech_to_text_tool, text_to_speech_tool


ALL_TOOLS = [
    rag_tool,
    web_search_tool,
    calculator_tool,
    summary_tool,
    vision_tool,
    speech_to_text_tool,
    text_to_speech_tool
]