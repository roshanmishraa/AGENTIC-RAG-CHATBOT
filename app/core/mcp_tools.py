from __future__ import annotations
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

from app.settings import settings

logger = logging.getLogger(__name__)

# ============================================================
# MCP Server Configuration
# ============================================================
# All three are free, official/community reference servers.
# Brave Search needs a free API key (2000 queries/month free tier).
MCP_CONFIG = {
    "fetch": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
    },
    "sequential_thinking": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
    },
}

# Brave Search only added if the API key is actually configured — avoids
# startup failures for people who haven't set it up yet.
if settings.BRAVE_SEARCH_API_KEY:
    MCP_CONFIG["brave_search"] = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": settings.BRAVE_SEARCH_API_KEY},
    }

_mcp_client: MultiServerMCPClient | None = None
MCP_TOOLS: list = []


async def load_mcp_tools() -> list:
    """
    Called once on app startup (from main.py lifespan).
    If any MCP server fails to connect, we log it and continue with an empty
    tool list — MCP is an enhancement, not a hard dependency for the app to run.
    """
    global _mcp_client, MCP_TOOLS

    if not MCP_CONFIG:
        logger.info("No MCP servers configured — skipping.")
        return []

    try:
        _mcp_client = MultiServerMCPClient(MCP_CONFIG)
        MCP_TOOLS = await _mcp_client.get_tools()
        logger.info(f"MCP tools loaded: {[t.name for t in MCP_TOOLS]}")
        return MCP_TOOLS
    except Exception as exc:
        logger.error(f"MCP tool loading failed, continuing without MCP tools: {exc}")
        MCP_TOOLS = []
        return []


def get_mcp_tools() -> list:
    return MCP_TOOLS
