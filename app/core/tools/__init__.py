from .rag_tool import rag_tool
from .search_tool import web_search_tool
from .calculator_tool import calculator_tool
from .summary_tool import summary_tool


ALL_TOOLS = [
    rag_tool,
    web_search_tool,
    calculator_tool,
    summary_tool,
]


def get_custom_tools():
    return ALL_TOOLS