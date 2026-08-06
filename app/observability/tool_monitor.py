from __future__ import annotations
import time
from app.observability.logger import get_logger

logger = get_logger(__name__)


async def execute_tool_with_observability(tool_obj, tool_call: dict) -> dict:
    """
    Wraps every tool execution with logging + timing — this is what makes
    tool calls actually observable. Every call, its latency, and its
    success/failure gets logged here, and (since it runs inside a
    LangGraph node) also shows up as a child span in the LangSmith trace.
    """
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_call_id = tool_call["id"]

    start = time.monotonic()
    try:
        result = await tool_obj.ainvoke(tool_args)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info("tool_call_completed", extra={"tool_name": tool_name, "duration_ms": duration_ms})
        return {
            "tool_call_id": tool_call_id, "tool_name": tool_name,
            "content": str(result), "success": True, "duration_ms": duration_ms,
        }
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error(f"tool_call_failed: {tool_name} — {exc}",
                     extra={"tool_name": tool_name, "duration_ms": duration_ms})
        return {
            "tool_call_id": tool_call_id, "tool_name": tool_name,
            "content": f"Tool execution failed: {exc}", "success": False, "duration_ms": duration_ms,
        }