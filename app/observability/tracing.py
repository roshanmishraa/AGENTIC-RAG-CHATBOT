from __future__ import annotations
import os
from app.settings import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


def setup_langsmith_tracing():
    """
    Called once at app startup. LangChain/LangGraph automatically pick up
    these env vars — no code changes needed in graph.py itself, every LLM
    call, tool call, and node execution gets traced automatically.
    """
    if not settings.LANGSMITH_API_KEY:
        logger.warning("LANGSMITH_API_KEY not set — tracing disabled. "
                        "Get a free key at smith.langchain.com")
        return False

    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT

    logger.info(f"LangSmith tracing enabled — project: {settings.LANGCHAIN_PROJECT}")
    return True


def get_trace_url(run_id: str) -> str:
    """Build a direct link to a specific trace — useful to return in admin
    debug views so you can jump straight to the LangSmith UI for a failed request."""
    return f"https://smith.langchain.com/o/default/projects/p/{settings.LANGCHAIN_PROJECT}/r/{run_id}"