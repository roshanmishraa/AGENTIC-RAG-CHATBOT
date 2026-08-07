from .rag_tool import make_rag_tool
from .search_tool import web_search_tool
from .calculator_tool import calculator_tool
from .summary_tool import summary_tool


def get_custom_tools(owner_id: str | None = None, document_ids: list[str] | None = None):
    """
    owner_id/document_ids are threaded through so rag_tool stays scoped to
    the requesting user even when the LLM invokes it as a tool call
    mid-conversation, not just on the initial retrieve() pass.
    """
    return [
        make_rag_tool(owner_id, document_ids),
        web_search_tool,
        calculator_tool,
        summary_tool,
    ]