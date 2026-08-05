from __future__ import annotations

from typing import (
    Optional, Dict, Any, List, Annotated, Callable,
    Union, Tuple, Awaitable, Coroutine
)
from pydantic import BaseModel, Field

# Make available globally - CRITICAL FIX
import builtins
import typing

# Set all types in builtins
builtins.Annotated = Annotated
builtins.Dict = Dict
builtins.Any = Any
builtins.Optional = Optional
builtins.List = List
builtins.Union = Union
builtins.Tuple = Tuple
builtins.Callable = Callable
builtins.Awaitable = Awaitable
builtins.Coroutine = Coroutine
builtins.BaseModel = BaseModel
builtins.Field = Field
builtins.ArgsSchema = BaseModel
builtins.typing = typing

# Handle SkipValidation
try:
    from pydantic import SkipValidation
    builtins.SkipValidation = SkipValidation
except ImportError:
    builtins.SkipValidation = type('SkipValidation', (), {})

# Make Annotated available in typing module too
if not hasattr(typing, 'Annotated'):
    typing.Annotated = Annotated

# Make it available in module globals
globals()['Annotated'] = Annotated
globals()['Callable'] = Callable

import asyncio
import inspect
import logging
import requests

# --------------------------------------------------
# Optional LangSmith tracing (safe fallback)
# --------------------------------------------------
try:
    from langsmith import traceable
except Exception:
    def traceable(*a, **kw):
        def deco(fn): 
            return fn
        return deco

# --------------------------------------------------
# LangChain tool decorator
# --------------------------------------------------
from langchain_core.tools import tool

from app.settings import settings

# Lazy MCP tools
try:
    from app.core.mcp_tools import MCP_TOOLS
except Exception:
    MCP_TOOLS = []

# Optional DuckDuckGo
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except Exception:
    DDGS_AVAILABLE = False

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Helper: run async or sync safely
# --------------------------------------------------
def run_maybe_async(result):
    """Run coroutine safely from sync or async context."""
    if not inspect.isawaitable(result):
        return result
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already inside an async context — submit to the backend loop
            from app.core.graph import submit_async_task
            future = submit_async_task(result)
            return future.result(timeout=30)
        return loop.run_until_complete(result)
    except RuntimeError:
        return asyncio.new_event_loop().run_until_complete(result)


# ==================================================
# 1) Calculator Tool
# ==================================================
# @traceable(name="calculator_tool", run_type="tool")
@tool
def calculator(
    first_num: float,
    second_num: float,
    operation: str,
) -> Dict[str, Any]:
    """
    Perform basic arithmetic operations.

    Args:
        first_num: First number
        second_num: Second number
        operation: Operation type - must be one of: add, sub, mul, div

    Returns:
        Calculation result or error message
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero"}
            result = first_num / second_num
        else:
            return {"error": "Invalid operation"}

        return {"operation": operation, "result": result}
    except Exception as e:
        logger.exception("Calculator failed")
        return {"error": str(e)}


# ==================================================
# 2) Stock Price Tool
# ==================================================
# @traceable(name="get_stock_price_tool", run_type="tool")
@tool
def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    Fetch latest stock price using Alpha Vantage API.

    Args:
        symbol: Stock ticker symbol (e.g., AAPL)

    Returns:
        Stock price data or error
    """
    if not settings.ALPHAVANTAGE_API_KEY:
        return {"error": "ALPHAVANTAGE_API_KEY missing"}

    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": settings.ALPHAVANTAGE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.exception("Stock fetch failed")
        return {"error": str(e)}


# ==================================================
# 3) Web Search Tool
# ==================================================
# @traceable(name="web_search_tool", run_type="tool")
@tool
def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query
        max_results: Number of results to return

    Returns:
        Search results or error
    """
    try:
        if DDGS_AVAILABLE:
            with DDGS() as ddg:
                results = list(ddg.text(query, max_results=max_results))
            return {"query": query, "results": results}

        resp = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            timeout=10,
        )
        return {"query": query, "html": resp.text[:2000]}
    except Exception as e:
        logger.exception("Web search failed")
        return {"error": str(e)}


# ==================================================
# 4) RAG Tool
# ==================================================
# @traceable(name="rag_tool", run_type="tool")
@tool
def rag_tool(
    query: str,
    thread_id: str,
    top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Retrieve relevant documents from Pinecone for a given thread.

    Args:
        query: User question
        thread_id: Conversation thread ID (required)
        top_k: Number of documents to retrieve (optional)

    Returns:
        Retrieved chunks with metadata
    """
    if not thread_id:
        return {"error": "thread_id required"}

    try:
        from app.core.rag import retrieve_for_thread, thread_document_metadata

        k = top_k or settings.RAG_K
        docs = run_maybe_async(retrieve_for_thread(thread_id, query, k))

        results = [
            {"text": d.page_content, "metadata": d.metadata}
            for d in docs or []
        ]

        return {
            "query": query,
            "results": results,
            "source": thread_document_metadata(thread_id),
        }
    except Exception as e:
        logger.exception("RAG failed")
        return {"error": str(e)}


# ==================================================
# Merge ALL tools
# ==================================================
ALL_TOOLS = [
    calculator,
    get_stock_price,
    web_search,
    rag_tool,
] + (MCP_TOOLS or [])

# DEBUG: Print all tools to see which one has the issue
if __name__ != "__main__":
    print("=" * 60)
    print("LOADED TOOLS:")
    for i, tool in enumerate(ALL_TOOLS):
        print(f"{i+1}. {tool.name if hasattr(tool, 'name') else tool}")
        if hasattr(tool, 'func'):
            import inspect
            sig = inspect.signature(tool.func)
            print(f"   Signature: {sig}")
    print("=" * 60)