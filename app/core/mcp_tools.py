from __future__ import annotations
from typing import Annotated
import asyncio
import inspect
import logging
import sys
import typing
from typing import Annotated, Dict, Any, Optional
from pydantic import BaseModel, Field

# Make available globally
import builtins
builtins.Annotated = Annotated
builtins.BaseModel = BaseModel
builtins.Field = Field

globals()['Annotated'] = typing.Annotated
# Try optional MCP adapter
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except Exception:
    MultiServerMCPClient = None

logger = logging.getLogger(__name__)

# ============================================================
# MCP Configuration (Disabled by default unless configured)
# ============================================================

DEFAULT_CONFIG = {
    # Example only. Disabled until user configures MCP scripts.
    # "arith": {
    #     "transport": "stdio",
    #     "command": sys.executable,  # safer than "python3"
    #     "args": ["arith_server.py"],
    # }
}

# Storage for loaded tools
MCP_TOOLS = []


# ============================================================
# Async loader
# ============================================================

async def _load_mcp_tools_async() -> list:
    """
    Load MCP tools from configured servers.
    This function is async and safe to call via run_async().
    """

    if MultiServerMCPClient is None:
        logger.info("MCP adapter not installed — skipping MCP tools.")
        return []

    if not DEFAULT_CONFIG:
        logger.info("No MCP servers configured — skipping MCP tools.")
        return []

    try:
        client = MultiServerMCPClient(DEFAULT_CONFIG)

        tools = client.get_tools()

        # get_tools can be sync or async
        if inspect.isawaitable(tools):
            tools = await tools

        # ✅ Fix namespace for each tool
        import typing
        for tool in (tools or []):
            try:
                # Try to inject Annotated into the tool's namespace
                if hasattr(tool, 'func') and hasattr(tool.func, '__globals__'):
                    tool.func.__globals__['Annotated'] = typing.Annotated
                elif callable(tool) and hasattr(tool, '__globals__'):
                    tool.__globals__['Annotated'] = typing.Annotated
            except Exception as e:
                logger.warning(f"Could not inject Annotated into tool namespace: {e}")

        logger.info(f"MCP tools loaded: {len(tools)}")
        return tools or []

    except Exception as exc:
        logger.error(f"MCP tool loading failed: {exc}", exc_info=True)
        return []


# ============================================================
# Public safe loader — called from main.py startup
# ============================================================

def load_mcp_tools_safely():
    """
    Load MCP tools using LangGraph’s backend event loop.
    This function MUST NOT block FastAPI's event loop.
    """

    from app.core.graph import run_async  # lazy import to avoid circular issues

    global MCP_TOOLS

    try:
        MCP_TOOLS = run_async(_load_mcp_tools_async()) or []
    except Exception as exc:
        logger.error(f"MCP tool load error: {exc}")
        MCP_TOOLS = []

    return MCP_TOOLS


# ============================================================
# IMPORTANT: No auto-load at import time!
# ============================================================
# (We intentionally DO NOT auto-load tools here.)
# Tools are loaded from main.py startup event.

