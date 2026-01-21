from __future__ import annotations  # ✅ MUST be first line

import os
import asyncio
import threading
from typing import Annotated, TypedDict, List, Optional
from pydantic import BaseModel, Field

# Make available globally
import builtins
builtins.Annotated = Annotated
builtins.BaseModel = BaseModel
builtins.Field = Field

from langchain_core.messages import BaseMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite

# Optional LangSmith tracing (safe fallback)
try:
    from langsmith import traceable
except Exception:
    def traceable(*a, **kw):
        def deco(fn): return fn
        return deco

from app.core.tools import ALL_TOOLS
from app.settings import settings


# =========================================================
# Backend event loop (for Streamlit / sync callers)
# =========================================================

_BACKEND_LOOP: Optional[asyncio.AbstractEventLoop] = None
_BACKEND_THREAD: Optional[threading.Thread] = None
_BACKEND_LOCK = threading.Lock()


def ensure_backend_running():
    """Ensure a dedicated asyncio loop is running in a background thread."""
    global _BACKEND_LOOP, _BACKEND_THREAD

    with _BACKEND_LOCK:
        if _BACKEND_LOOP and _BACKEND_THREAD and _BACKEND_THREAD.is_alive():
            return

        _BACKEND_LOOP = asyncio.new_event_loop()

        def _run():
            asyncio.set_event_loop(_BACKEND_LOOP)
            _BACKEND_LOOP.run_forever()

        _BACKEND_THREAD = threading.Thread(target=_run, daemon=True)
        _BACKEND_THREAD.start()


def run_async(coro):
    """Run coroutine on backend loop and BLOCK until result."""
    ensure_backend_running()
    return asyncio.run_coroutine_threadsafe(coro, _BACKEND_LOOP).result()


def submit_async_task(coro):
    """
    ✅ THIS WAS MISSING
    Submit coroutine to backend loop WITHOUT blocking.
    Returns concurrent.futures.Future
    """
    ensure_backend_running()
    return asyncio.run_coroutine_threadsafe(coro, _BACKEND_LOOP)


# =========================================================
# LLM (lazy, single instance)
# =========================================================

_llm: Optional[ChatOpenAI] = None
_llm_with_tools = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )
    return _llm


def get_llm_with_tools():
    global _llm_with_tools
    if _llm_with_tools is None:
        try:
            _llm_with_tools = get_llm().bind_tools(ALL_TOOLS)
        except Exception:
            _llm_with_tools = get_llm()
    return _llm_with_tools


# =========================================================
# Graph State (MEMORY ENABLED)
# =========================================================

class ChatState(TypedDict):
    # add_messages ensures full conversation memory
    messages: Annotated[List[BaseMessage], add_messages]


# =========================================================
# Chat Node (LLM)
# =========================================================

@traceable(name="chat_node", run_type="llm")
async def chat_node(state: ChatState, config=None):
    # Get thread_id from config
    thread_id = None
    has_document = False
    
    if config:
        thread_id = config.get("configurable", {}).get("thread_id")
        
        # Check if document exists for this thread
        if thread_id:
            try:
                from app.core.rag import thread_has_document
                has_document = thread_has_document(thread_id)
            except Exception:
                pass
    
    # Build system prompt based on whether document exists
    if has_document and thread_id:
        system_prompt = (
            "You are an intelligent AI assistant with access to tools.\n\n"
            "⚠️ CRITICAL: A document has been uploaded and indexed for this conversation.\n"
            "You MUST use the rag_tool to search the document before answering questions.\n\n"
            "MANDATORY WORKFLOW:\n"
            "1. For ANY user question, first call rag_tool to search the uploaded document\n"
            f"2. Use these exact parameters: query='<user question>', thread_id='{thread_id}'\n"
            "3. After receiving search results, answer based on the retrieved information\n"
            "4. If the document doesn't contain relevant info, state that clearly\n\n"
            "Available tools:\n"
            "- rag_tool: Search the uploaded document (ALWAYS USE THIS FIRST)\n"
            "- calculator: Perform math operations\n"
            "- web_search: Search the internet\n"
            "- get_stock_price: Get stock prices\n"
        )
    else:
        system_prompt = (
            "You are an intelligent AI assistant with access to tools.\n"
            "Rules:\n"
            "- Use tools when they would be helpful\n"
            "- Keep answers concise and accurate\n"
            "- For calculations, use the calculator tool\n"
            "- For current info, use web_search\n"
        )

    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    try:
        llm = get_llm_with_tools()
        response = await llm.ainvoke(messages, config=config)
        return {"messages": [response]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"LLM error: {e}")]}


# =========================================================
# Tool Node (LangGraph native)
# =========================================================

def get_tool_node():
    return ToolNode(ALL_TOOLS) if ALL_TOOLS else None


# =========================================================
# Checkpointer (SQLite, async)
# =========================================================

_checkpointer = None


async def _init_checkpointer():
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    os.makedirs(os.path.dirname(settings.CHECKPOINT_DB_PATH), exist_ok=True)
    
    # ✅ Fix: Add check_same_thread=False
    conn = await aiosqlite.connect(
        settings.CHECKPOINT_DB_PATH,
        check_same_thread=False  # This allows cross-thread access
    )
    _checkpointer = AsyncSqliteSaver(conn)
    
    # ✅ Initialize the checkpointer in the current loop
    try:
        await _checkpointer.setup()
    except Exception:
        pass  # setup might not exist in all versions
    
    return _checkpointer


def get_checkpointer():
    return run_async(_init_checkpointer())


# =========================================================
# Graph compilation (lazy, cached)
# =========================================================

_compiled_graph = None


async def _build_graph():
    global _compiled_graph

    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(ChatState)

    graph.add_node("chat", chat_node)
    graph.add_edge(START, "chat")

    tool_node = get_tool_node()
    if tool_node:
        graph.add_node("tools", tool_node)
        graph.add_conditional_edges("chat", tools_condition)
        graph.add_edge("tools", "chat")
    else:
        graph.add_edge("chat", END)

    saver = await _init_checkpointer()
    _compiled_graph = graph.compile(checkpointer=saver)

    return _compiled_graph


def get_compiled_chatbot():
    return run_async(_build_graph())


# =========================================================
# Proxy (prevents heavy import-time init)
# =========================================================

class _ChatbotProxy:
    def __getattr__(self, name):
        return getattr(get_compiled_chatbot(), name)

    def __call__(self, *a, **kw):
        return get_compiled_chatbot()(*a, **kw)


chatbot = _ChatbotProxy()

class _CheckpointerProxy:
    """
    Lazy proxy for checkpointer so legacy imports
    (langgraph_mcp_backend) do not break.
    """
    def __getattr__(self, name):
        saver = get_checkpointer()
        return getattr(saver, name)

_checkpointer_ref = _CheckpointerProxy()

